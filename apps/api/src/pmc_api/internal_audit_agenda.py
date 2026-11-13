"""Versioned UTC audit agenda; planning only, never execution authority."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.internal_audits import Name, Narrative, _audit, _audit_values, _db_error
from pmc_api.models import QMSAuditAgendaItem, QMSAuditScope, QMSAuditTeamMember, QMSInternalAudit
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits/audits", tags=["internal-audit-agenda"])
DB = Annotated[Session, Depends(get_db)]


class AgendaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    sequence: int = Field(ge=1, le=10000)
    title: Name
    objective: Narrative = ""
    method: Literal["interview", "observation", "document_review", "sampling", "meeting", "other"]
    location: Annotated[str, Field(max_length=240)] = ""
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    scope_id: UUID | None = None
    auditor_team_member_id: UUID
    auditee_team_member_id: UUID | None = None

    @model_validator(mode="after")
    def times(self) -> AgendaInput:
        self.starts_at, self.ends_at = self.starts_at.astimezone(UTC), self.ends_at.astimezone(UTC)
        if self.starts_at >= self.ends_at or any(
            t.second or t.microsecond for t in (self.starts_at, self.ends_at)
        ):
            raise ValueError("agenda requires ordered UTC times at minute precision")
        return self


class AgendaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    sequence: int | None = Field(default=None, ge=1, le=10000)
    title: Name | None = None
    objective: Narrative | None = None
    method: (
        Literal["interview", "observation", "document_review", "sampling", "meeting", "other"]
        | None
    ) = None
    location: Annotated[str | None, Field(max_length=240)] = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    scope_id: UUID | None = None
    auditor_team_member_id: UUID | None = None
    auditee_team_member_id: UUID | None = None

    @model_validator(mode="after")
    def changes(self) -> AgendaPatch:
        fields = self.model_fields_set - {"expected_version", "expected_audit_version"}
        if not fields or any(
            getattr(self, f) is None for f in fields - {"scope_id", "auditee_team_member_id"}
        ):
            raise ValueError("provide valid agenda changes")
        for name in {"starts_at", "ends_at"} & fields:
            value = getattr(self, name).astimezone(UTC)
            if value.second or value.microsecond:
                raise ValueError("agenda times use minute precision")
            setattr(self, name, value)
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValueError("end must follow start")
        return self


class AgendaWithdrawal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def reason_required(self) -> AgendaWithdrawal:
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("provide a withdrawal reason")
        return self


class AgendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    audit_id: UUID
    sequence: int
    title: str
    objective: str
    method: str
    location: str
    starts_at: datetime
    ends_at: datetime
    scope_id: UUID | None
    auditor_team_member_id: UUID
    auditee_team_member_id: UUID | None
    auditor_name: str = ""
    auditee_name: str | None = None
    status: str
    row_version: int
    withdrawal_reason: str
    withdrawn_by_user_id: UUID | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgendaResult(BaseModel):
    item: AgendaRead
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
            raise HTTPException(409, "audit changed; refresh before changing agenda")
        if parent.state not in {"draft", "planned"}:
            raise HTTPException(409, "audit planning is closed")
    return actor, parent


def _item(
    db: Session, parent: QMSInternalAudit, agenda_id: UUID, version: int
) -> QMSAuditAgendaItem:
    row = db.scalar(
        select(QMSAuditAgendaItem)
        .where(
            QMSAuditAgendaItem.id == agenda_id,
            QMSAuditAgendaItem.audit_id == parent.id,
            QMSAuditAgendaItem.tenant_id == parent.tenant_id,
            QMSAuditAgendaItem.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "audit agenda not found")
    if row.row_version != version or row.status != "active":
        raise HTTPException(409, "agenda changed or withdrawn; refresh before editing")
    return row


def _targets(
    db: Session,
    parent: QMSInternalAudit,
    scope_id: UUID | None,
    auditor_id: UUID,
    auditee_id: UUID | None,
) -> None:
    if (
        scope_id is not None
        and db.scalar(
            select(QMSAuditScope).where(
                QMSAuditScope.id == scope_id,
                QMSAuditScope.audit_id == parent.id,
                QMSAuditScope.tenant_id == parent.tenant_id,
                QMSAuditScope.unit_id == parent.unit_id,
                QMSAuditScope.status == "active",
            )
        )
        is None
    ):
        raise HTTPException(404, "active agenda scope not found")
    for person, role in [(auditor_id, "auditor"), (auditee_id, "auditee")]:
        if (
            person is not None
            and db.scalar(
                select(QMSAuditTeamMember).where(
                    QMSAuditTeamMember.id == person,
                    QMSAuditTeamMember.audit_id == parent.id,
                    QMSAuditTeamMember.tenant_id == parent.tenant_id,
                    QMSAuditTeamMember.unit_id == parent.unit_id,
                    QMSAuditTeamMember.status == "active",
                    QMSAuditTeamMember.team_role == role,
                )
            )
            is None
        ):
            raise HTTPException(404, "active agenda participant not found")


def _reads(
    db: Session, parent: QMSInternalAudit, rows: list[QMSAuditAgendaItem]
) -> list[AgendaRead]:
    ids = {row.auditor_team_member_id for row in rows} | {
        row.auditee_team_member_id for row in rows if row.auditee_team_member_id
    }
    if not ids:
        return []
    names: dict[UUID, str] = {
        entry.id: entry.display_name_snapshot
        for entry in db.execute(
            select(QMSAuditTeamMember.id, QMSAuditTeamMember.display_name_snapshot).where(
                QMSAuditTeamMember.id.in_(ids),
                QMSAuditTeamMember.audit_id == parent.id,
                QMSAuditTeamMember.tenant_id == parent.tenant_id,
                QMSAuditTeamMember.unit_id == parent.unit_id,
            )
        ).all()
    }
    result = []
    for row in rows:
        if (
            row.auditor_team_member_id not in names
            or row.auditee_team_member_id
            and row.auditee_team_member_id not in names
        ):
            raise HTTPException(404, "agenda participant history unavailable")
        result.append(
            AgendaRead.model_validate(row).model_copy(
                update={
                    "auditor_name": names[row.auditor_team_member_id],
                    "auditee_name": names.get(row.auditee_team_member_id)
                    if row.auditee_team_member_id
                    else None,
                }
            )
        )
    return result


def _values(parent: QMSInternalAudit, row: QMSAuditAgendaItem) -> dict[str, object]:
    values = _audit_values(parent)
    values.update(
        agenda_id=str(row.id),
        agenda_sequence=row.sequence,
        agenda_title_hash=hashlib.sha256(row.title.encode()).hexdigest(),
        agenda_objective_hash=hashlib.sha256(row.objective.encode()).hexdigest(),
        agenda_location_hash=hashlib.sha256(row.location.encode()).hexdigest(),
        agenda_method=row.method,
        agenda_starts_at=row.starts_at.astimezone(UTC).isoformat(),
        agenda_ends_at=row.ends_at.astimezone(UTC).isoformat(),
        agenda_scope_id=str(row.scope_id) if row.scope_id else None,
        agenda_auditor_id=str(row.auditor_team_member_id),
        agenda_auditee_id=str(row.auditee_team_member_id) if row.auditee_team_member_id else None,
        agenda_version=row.row_version,
        agenda_status=row.status,
        agenda_withdrawal_reason_hash=hashlib.sha256(row.withdrawal_reason.encode()).hexdigest(),
    )
    return values


def _save(
    db: Session,
    request: Request,
    actor: OrganizationActor,
    parent: QMSInternalAudit,
    row: QMSAuditAgendaItem,
    before: dict[str, object] | None,
) -> AgendaResult:
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
        result = AgendaResult(item=_reads(db, parent, [row])[0], audit_version=parent.row_version)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return result


@router.get("/{audit_id}/agenda", response_model=list[AgendaRead])
def list_agenda(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    status: Annotated[str | None, Query(pattern="^(active|withdrawn)$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[AgendaRead]:
    _, parent = _parent(db, authenticated, audit_id)
    query = select(QMSAuditAgendaItem).where(
        QMSAuditAgendaItem.audit_id == parent.id,
        QMSAuditAgendaItem.tenant_id == parent.tenant_id,
        QMSAuditAgendaItem.unit_id == parent.unit_id,
    )
    if status:
        query = query.where(QMSAuditAgendaItem.status == status)
    return _reads(
        db,
        parent,
        list(
            db.scalars(
                query.order_by(
                    QMSAuditAgendaItem.starts_at, QMSAuditAgendaItem.sequence, QMSAuditAgendaItem.id
                )
                .limit(limit)
                .offset(offset)
            )
        ),
    )


@router.post(
    "/{audit_id}/agenda",
    response_model=AgendaResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_agenda_item(
    audit_id: UUID, body: AgendaInput, request: Request, db: DB, authenticated: Authenticated
) -> AgendaResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    _targets(db, parent, body.scope_id, body.auditor_team_member_id, body.auditee_team_member_id)
    now = datetime.now(UTC)
    row = QMSAuditAgendaItem(
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
    "/{audit_id}/agenda/{agenda_id}",
    response_model=AgendaResult,
    dependencies=[Depends(require_csrf)],
)
def update_agenda_item(
    audit_id: UUID,
    agenda_id: UUID,
    body: AgendaPatch,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> AgendaResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, agenda_id, body.expected_version)
    before = _values(parent, row)
    changes = body.model_dump(
        exclude={"expected_audit_version", "expected_version"}, exclude_unset=True
    )
    _targets(
        db,
        parent,
        changes.get("scope_id", row.scope_id),
        changes.get("auditor_team_member_id", row.auditor_team_member_id),
        changes.get("auditee_team_member_id", row.auditee_team_member_id),
    )
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, request, actor, parent, row, before)


@router.post(
    "/{audit_id}/agenda/{agenda_id}/withdraw",
    response_model=AgendaResult,
    dependencies=[Depends(require_csrf)],
)
def withdraw_agenda_item(
    audit_id: UUID,
    agenda_id: UUID,
    body: AgendaWithdrawal,
    request: Request,
    db: DB,
    authenticated: Authenticated,
) -> AgendaResult:
    actor, parent = _parent(db, authenticated, audit_id, body.expected_audit_version)
    row = _item(db, parent, agenda_id, body.expected_version)
    before = _values(parent, row)
    row.status = "withdrawn"
    row.withdrawal_reason = body.reason
    row.withdrawn_by_user_id = actor.user_id
    row.withdrawn_at = row.updated_at = datetime.now(UTC)
    row.row_version += 1
    return _save(db, request, actor, parent, row, before)
