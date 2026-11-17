"""Audit criteria; parent versions and narrative hashes commit atomically."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.internal_audits import Name, _audit, _audit_values, _db_error
from pmc_api.models import QMSAuditCriterion, QMSAuditScope, QMSInternalAudit
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits/audits", tags=["internal-audit-criterion"])
DB = Annotated[Session, Depends(get_db)]


class CriterionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    sequence: int = Field(ge=1, le=10000)
    title: Name
    requirement: Annotated[str, Field(min_length=1, max_length=4000)]
    source_type: Literal["internal", "standard", "regulation", "customer"]
    reference: Annotated[str, Field(min_length=1, max_length=240)]
    scope_id: UUID | None = None

    @model_validator(mode="after")
    def authored_fields(self) -> CriterionInput:
        self.requirement = self.requirement.strip()
        self.reference = self.reference.strip()
        if not self.requirement or not self.reference:
            raise ValueError("provide authored requirement and source reference")
        return self


class CriterionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    sequence: int | None = Field(default=None, ge=1, le=10000)
    title: Name | None = None
    requirement: Annotated[str | None, Field(min_length=1, max_length=4000)] = None
    source_type: Literal["internal", "standard", "regulation", "customer"] | None = None
    reference: Annotated[str | None, Field(min_length=1, max_length=240)] = None
    scope_id: UUID | None = None

    @model_validator(mode="after")
    def changes(self) -> CriterionPatch:
        fields = self.model_fields_set - {"expected_version", "expected_audit_version"}
        if not fields or any(getattr(self, f) is None for f in fields - {"scope_id"}):
            raise ValueError("provide valid criterion changes")
        for name in {"requirement", "reference"} & fields:
            value = getattr(self, name).strip()
            if not value:
                raise ValueError("provide authored requirement and source reference")
            setattr(self, name, value)
        return self


class CriterionWithdrawal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def reason_required(self) -> CriterionWithdrawal:
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("provide a withdrawal reason")
        return self


class CriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    audit_id: UUID
    sequence: int
    title: str
    requirement: str
    source_type: str
    reference: str
    scope_id: UUID | None
    status: str
    row_version: int
    withdrawal_reason: str
    withdrawn_by_user_id: UUID | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CriterionResult(BaseModel):
    criterion: CriterionRead
    audit_version: int


def _parent(
    db: Session, auth: Authenticated, audit_id: UUID, version: int | None = None
) -> tuple[OrganizationActor, QMSInternalAudit]:
    actor = actor_context(db, auth)
    parent = _audit(db, actor, audit_id)
    if version is not None:
        require_capability(db, "audits.manage", parent.unit_id)
        parent = _audit(db, actor, audit_id, lock=True)
        if parent.row_version != version:
            raise HTTPException(409, "audit changed; refresh before changing criterion")
        if parent.state not in {"draft", "planned"}:
            raise HTTPException(409, "audit planning is closed")
    return actor, parent


def _item(
    db: Session, parent: QMSInternalAudit, criterion_id: UUID, version: int
) -> QMSAuditCriterion:
    row = db.scalar(
        select(QMSAuditCriterion)
        .where(
            QMSAuditCriterion.id == criterion_id,
            QMSAuditCriterion.audit_id == parent.id,
            QMSAuditCriterion.tenant_id == parent.tenant_id,
            QMSAuditCriterion.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "audit criterion not found")
    if row.row_version != version or row.status != "active":
        raise HTTPException(409, "criterion changed or withdrawn; refresh before editing")
    return row


def _scope(db: Session, parent: QMSInternalAudit, scope_id: UUID | None) -> None:
    if scope_id is None:
        return
    row = db.scalar(
        select(QMSAuditScope)
        .where(
            QMSAuditScope.id == scope_id,
            QMSAuditScope.audit_id == parent.id,
            QMSAuditScope.tenant_id == parent.tenant_id,
            QMSAuditScope.unit_id == parent.unit_id,
            QMSAuditScope.status == "active",
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "criterion scope not found")


def _values(parent: QMSInternalAudit, row: QMSAuditCriterion) -> dict[str, object]:
    values = _audit_values(parent)
    values.update(
        criterion_id=str(row.id),
        criterion_sequence=row.sequence,
        criterion_title_hash=hashlib.sha256(row.title.encode()).hexdigest(),
        criterion_requirement_hash=hashlib.sha256(row.requirement.encode()).hexdigest(),
        criterion_reference_hash=hashlib.sha256(row.reference.encode()).hexdigest(),
        criterion_source_type=row.source_type,
        criterion_scope_id=str(row.scope_id) if row.scope_id else None,
        criterion_version=row.row_version,
        criterion_status=row.status,
        criterion_withdrawal_reason_hash=hashlib.sha256(row.withdrawal_reason.encode()).hexdigest(),
    )
    return values


def _save(
    db: Session,
    request: Request,
    actor: OrganizationActor,
    parent: QMSInternalAudit,
    row: QMSAuditCriterion,
    before: dict[str, object] | None,
) -> CriterionResult:
    try:
        db.add(row)
        db.flush()
        db.refresh(parent)  # SQL trigger advances the parent even for direct SQL writes.
        audit_service.record_internal_audit(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action="internal_audit.updated",
            resource_id=parent.id,
            request_id=request.state.request_id,
            old_values=before,
            new_values=_values(parent, row),
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return CriterionResult(
        criterion=CriterionRead.model_validate(row), audit_version=parent.row_version
    )


@router.get("/{audit_id}/criteria", response_model=list[CriterionRead])
def list_criteria(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    status: Annotated[str | None, Query(pattern="^(active|withdrawn)$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditCriterion]:
    _, parent = _parent(db, authenticated, audit_id)
    query = select(QMSAuditCriterion).where(
        QMSAuditCriterion.audit_id == parent.id,
        QMSAuditCriterion.tenant_id == parent.tenant_id,
        QMSAuditCriterion.unit_id == parent.unit_id,
    )
    if status:
        query = query.where(QMSAuditCriterion.status == status)
    return list(
        db.scalars(
            query.order_by(QMSAuditCriterion.sequence, QMSAuditCriterion.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/{audit_id}/criteria",
    response_model=CriterionResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_criterion(
    audit_id: UUID, body: CriterionInput, request: Request, db: DB, authenticated: Authenticated
) -> CriterionResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    _scope(db, parent, body.scope_id)
    now = datetime.now(UTC)
    row = QMSAuditCriterion(
        id=uuid4(),
        tenant_id=parent.tenant_id,
        unit_id=parent.unit_id,
        audit_id=parent.id,
        **body.model_dump(exclude={"expected_audit_version"}),
        status="active",
        row_version=1,
        withdrawal_reason="",
        withdrawn_at=None,
        withdrawn_by_user_id=None,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    return _save(db, request, actor, parent, row, _audit_values(parent))


@router.patch(
    "/{audit_id}/criteria/{criterion_id}",
    response_model=CriterionResult,
    dependencies=[Depends(require_csrf)],
)
def update_criterion(
    audit_id: UUID,
    criterion_id: UUID,
    body: CriterionPatch,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> CriterionResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, criterion_id, body.expected_version)
    before = _values(parent, row)
    changes = body.model_dump(
        exclude={"expected_audit_version", "expected_version"}, exclude_unset=True
    )
    _scope(db, parent, changes.get("scope_id", row.scope_id))
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, request, actor, parent, row, before)


@router.post(
    "/{audit_id}/criteria/{criterion_id}/withdraw",
    response_model=CriterionResult,
    dependencies=[Depends(require_csrf)],
)
def withdraw_criterion(
    audit_id: UUID,
    criterion_id: UUID,
    body: CriterionWithdrawal,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> CriterionResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, criterion_id, body.expected_version)
    before = _values(parent, row)
    row.status = "withdrawn"
    row.withdrawal_reason = body.reason
    row.withdrawn_by_user_id = actor.user_id
    row.withdrawn_at = row.updated_at = datetime.now(UTC)
    row.row_version += 1
    return _save(db, request, actor, parent, row, before)
