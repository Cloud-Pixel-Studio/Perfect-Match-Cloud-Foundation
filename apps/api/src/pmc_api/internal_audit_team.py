"""Internal-audit planning team with explicit, versioned assignment history."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.internal_audits import Narrative, _audit, _audit_values, _db_error
from pmc_api.models import QMSAuditTeamMember, QMSInternalAudit
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits/audits", tags=["internal-audit-team"])
DB = Annotated[Session, Depends(get_db)]


class TeamInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    user_id: UUID
    team_role: Literal["auditor", "auditee"]
    responsibilities: Narrative = ""


class TeamPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    team_role: Literal["auditor", "auditee"] | None = None
    responsibilities: Narrative | None = None

    @model_validator(mode="after")
    def changes(self) -> TeamPatch:
        fields = self.model_fields_set - {"expected_version", "expected_audit_version"}
        if not fields or any(getattr(self, f) is None for f in fields):
            raise ValueError("provide valid team changes")
        return self


class TeamWithdrawal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def reason_required(self) -> TeamWithdrawal:
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("provide a withdrawal reason")
        return self


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    audit_id: UUID
    user_id: UUID
    display_name_snapshot: str
    team_role: str
    responsibilities: str
    status: str
    row_version: int
    withdrawal_reason: str
    withdrawn_by_user_id: UUID | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TeamResult(BaseModel):
    member: TeamRead
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
            raise HTTPException(409, "audit changed; refresh before changing team")
        if parent.state not in {"draft", "planned"}:
            raise HTTPException(409, "audit planning is closed")
    return actor, parent


def _item(db: Session, parent: QMSInternalAudit, team_id: UUID, version: int) -> QMSAuditTeamMember:
    row = db.scalar(
        select(QMSAuditTeamMember)
        .where(
            QMSAuditTeamMember.id == team_id,
            QMSAuditTeamMember.audit_id == parent.id,
            QMSAuditTeamMember.tenant_id == parent.tenant_id,
            QMSAuditTeamMember.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "audit team not found")
    if row.row_version != version or row.status != "active":
        raise HTTPException(409, "team changed or withdrawn; refresh before editing")
    return row


def _member_name(db: Session, user_id: UUID) -> str:
    name = db.scalar(
        text("SELECT display_name FROM organization_member_directory() WHERE user_id=:id"),
        {"id": user_id},
    )
    if name is None:
        raise HTTPException(404, "active company member not found")
    return str(name)


def _values(parent: QMSInternalAudit, row: QMSAuditTeamMember) -> dict[str, object]:
    values = _audit_values(parent)
    values.update(
        team_member_id=str(row.id),
        team_user_id=str(row.user_id),
        team_role=row.team_role,
        team_display_name_hash=hashlib.sha256(row.display_name_snapshot.encode()).hexdigest(),
        team_responsibilities_hash=hashlib.sha256(row.responsibilities.encode()).hexdigest(),
        team_version=row.row_version,
        team_status=row.status,
        team_withdrawal_reason_hash=hashlib.sha256(row.withdrawal_reason.encode()).hexdigest(),
    )
    return values


def _save(
    db: Session,
    request: Request,
    actor: OrganizationActor,
    parent: QMSInternalAudit,
    row: QMSAuditTeamMember,
    before: dict[str, object] | None,
) -> TeamResult:
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
    return TeamResult(member=TeamRead.model_validate(row), audit_version=parent.row_version)


@router.get("/{audit_id}/team-members", response_model=list[TeamRead])
def list_team_members(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    status: Annotated[str | None, Query(pattern="^(active|withdrawn)$")] = None,
    team_role: Annotated[Literal["auditor", "auditee"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditTeamMember]:
    _, parent = _parent(db, authenticated, audit_id)
    query = select(QMSAuditTeamMember).where(
        QMSAuditTeamMember.audit_id == parent.id,
        QMSAuditTeamMember.tenant_id == parent.tenant_id,
        QMSAuditTeamMember.unit_id == parent.unit_id,
    )
    if status:
        query = query.where(QMSAuditTeamMember.status == status)
    if team_role:
        query = query.where(QMSAuditTeamMember.team_role == team_role)
    return list(
        db.scalars(
            query.order_by(QMSAuditTeamMember.team_role, QMSAuditTeamMember.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/{audit_id}/team-members",
    response_model=TeamResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_team_member(
    audit_id: UUID, body: TeamInput, request: Request, db: DB, authenticated: Authenticated
) -> TeamResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    display_name = _member_name(db, body.user_id)
    now = datetime.now(UTC)
    row = QMSAuditTeamMember(
        id=uuid4(),
        tenant_id=parent.tenant_id,
        unit_id=parent.unit_id,
        audit_id=parent.id,
        display_name_snapshot=display_name,
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
    "/{audit_id}/team-members/{team_id}",
    response_model=TeamResult,
    dependencies=[Depends(require_csrf)],
)
def update_team_member(
    audit_id: UUID,
    team_id: UUID,
    body: TeamPatch,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> TeamResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, team_id, body.expected_version)
    before = _values(parent, row)
    changes = body.model_dump(
        exclude={"expected_audit_version", "expected_version"}, exclude_unset=True
    )
    _member_name(db, row.user_id)
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, request, actor, parent, row, before)


@router.post(
    "/{audit_id}/team-members/{team_id}/withdraw",
    response_model=TeamResult,
    dependencies=[Depends(require_csrf)],
)
def withdraw_team_member(
    audit_id: UUID,
    team_id: UUID,
    body: TeamWithdrawal,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> TeamResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, team_id, body.expected_version)
    before = _values(parent, row)
    row.status = "withdrawn"
    row.withdrawal_reason = body.reason
    row.withdrawn_by_user_id = actor.user_id
    row.withdrawn_at = row.updated_at = datetime.now(UTC)
    row.row_version += 1
    return _save(db, request, actor, parent, row, before)
