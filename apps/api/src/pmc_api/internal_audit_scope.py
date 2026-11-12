"""Structured audit scope; changes version and audit the parent atomically."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.internal_audits import Name, Narrative, _audit, _audit_values, _db_error
from pmc_api.models import QMSAuditScope, QMSInternalAudit, QMSProcess
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits/audits", tags=["internal-audit-scope"])
DB = Annotated[Session, Depends(get_db)]


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    sequence: int = Field(ge=1, le=10000)
    title: Name
    description: Narrative = ""
    process_id: UUID | None = None


class ScopePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    sequence: int | None = Field(default=None, ge=1, le=10000)
    title: Name | None = None
    description: Narrative | None = None
    process_id: UUID | None = None

    @model_validator(mode="after")
    def changes(self) -> ScopePatch:
        fields = self.model_fields_set - {"expected_version", "expected_audit_version"}
        if not fields or any(getattr(self, f) is None for f in fields - {"process_id"}):
            raise ValueError("provide valid scope changes")
        return self


class ScopeWithdrawal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def reason_required(self) -> ScopeWithdrawal:
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("provide a withdrawal reason")
        return self


class ScopeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    audit_id: UUID
    sequence: int
    title: str
    description: str
    process_id: UUID | None
    status: str
    row_version: int
    withdrawal_reason: str
    withdrawn_by_user_id: UUID | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScopeResult(BaseModel):
    scope: ScopeRead
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
            raise HTTPException(409, "audit changed; refresh before changing scope")
        if parent.state not in {"draft", "planned"}:
            raise HTTPException(409, "audit planning is closed")
    return actor, parent


def _item(db: Session, parent: QMSInternalAudit, scope_id: UUID, version: int) -> QMSAuditScope:
    row = db.scalar(
        select(QMSAuditScope)
        .where(
            QMSAuditScope.id == scope_id,
            QMSAuditScope.audit_id == parent.id,
            QMSAuditScope.tenant_id == parent.tenant_id,
            QMSAuditScope.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "audit scope not found")
    if row.row_version != version or row.status != "active":
        raise HTTPException(409, "scope changed or withdrawn; refresh before editing")
    return row


def _process(db: Session, parent: QMSInternalAudit, process_id: UUID | None) -> None:
    if process_id is None:
        return
    require_capability(db, "processes.read", parent.unit_id)
    if (
        db.scalar(
            select(QMSProcess).where(
                QMSProcess.id == process_id,
                QMSProcess.tenant_id == parent.tenant_id,
                QMSProcess.unit_id == parent.unit_id,
                QMSProcess.status == "active",
            )
        )
        is None
    ):
        raise HTTPException(404, "scope process not found")


def _values(parent: QMSInternalAudit, row: QMSAuditScope) -> dict[str, object]:
    values = _audit_values(parent)
    values.update(
        scope_id=str(row.id),
        scope_sequence=row.sequence,
        scope_title_hash=hashlib.sha256(row.title.encode()).hexdigest(),
        scope_description_hash=hashlib.sha256(row.description.encode()).hexdigest(),
        scope_process_id=str(row.process_id) if row.process_id else None,
        scope_version=row.row_version,
        scope_status=row.status,
        scope_withdrawal_reason_hash=hashlib.sha256(row.withdrawal_reason.encode()).hexdigest(),
    )
    return values


def _save(
    db: Session,
    request: Request,
    actor: OrganizationActor,
    parent: QMSInternalAudit,
    row: QMSAuditScope,
    before: dict[str, object] | None,
) -> ScopeResult:
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
    return ScopeResult(scope=ScopeRead.model_validate(row), audit_version=parent.row_version)


@router.get("/{audit_id}/scopes", response_model=list[ScopeRead])
def list_scopes(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    status: Annotated[str | None, Query(pattern="^(active|withdrawn)$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditScope]:
    _, parent = _parent(db, authenticated, audit_id)
    query = select(QMSAuditScope).where(
        QMSAuditScope.audit_id == parent.id,
        QMSAuditScope.tenant_id == parent.tenant_id,
        QMSAuditScope.unit_id == parent.unit_id,
    )
    if status:
        query = query.where(QMSAuditScope.status == status)
    return list(
        db.scalars(
            query.order_by(QMSAuditScope.sequence, QMSAuditScope.id).limit(limit).offset(offset)
        )
    )


@router.post(
    "/{audit_id}/scopes",
    response_model=ScopeResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_scope(
    audit_id: UUID, body: ScopeInput, request: Request, db: DB, authenticated: Authenticated
) -> ScopeResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    _process(db, parent, body.process_id)
    now = datetime.now(UTC)
    row = QMSAuditScope(
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
    "/{audit_id}/scopes/{scope_id}",
    response_model=ScopeResult,
    dependencies=[Depends(require_csrf)],
)
def update_scope(
    audit_id: UUID,
    scope_id: UUID,
    body: ScopePatch,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> ScopeResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, scope_id, body.expected_version)
    before = _values(parent, row)
    changes = body.model_dump(
        exclude={"expected_audit_version", "expected_version"}, exclude_unset=True
    )
    _process(db, parent, changes.get("process_id", row.process_id))
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, request, actor, parent, row, before)


@router.post(
    "/{audit_id}/scopes/{scope_id}/withdraw",
    response_model=ScopeResult,
    dependencies=[Depends(require_csrf)],
)
def withdraw_scope(
    audit_id: UUID,
    scope_id: UUID,
    body: ScopeWithdrawal,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> ScopeResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, scope_id, body.expected_version)
    before = _values(parent, row)
    row.status = "withdrawn"
    row.withdrawal_reason = body.reason
    row.withdrawn_by_user_id = actor.user_id
    row.withdrawn_at = row.updated_at = datetime.now(UTC)
    row.row_version += 1
    return _save(db, request, actor, parent, row, before)
