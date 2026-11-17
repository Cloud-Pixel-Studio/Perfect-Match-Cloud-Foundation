"""Internal-audit programs and planning with explicit scoped authority."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import QMSAuditProgram, QMSInternalAudit
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits", tags=["internal-audits"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Narrative = Annotated[str, StringConstraints(max_length=4000)]
Decision = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
AuditType = Annotated[
    str, StringConstraints(pattern="^(system|process|department|special|follow_up)$")
]
ProgramState = Annotated[str, StringConstraints(pattern="^(approved|active|completed|cancelled)$")]
AuditPlanningState = Annotated[str, StringConstraints(pattern="^(planned|cancelled)$")]


class ProgramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    code: Code
    name: Name
    objective: Narrative = ""
    description: Narrative = ""
    date_start: date
    date_end: date
    owner_user_id: UUID | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> ProgramInput:
        if self.date_end < self.date_start:
            raise ValueError("audit program end date cannot precede its start date")
        return self


class ProgramPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: Name | None = None
    objective: Narrative | None = None
    description: Narrative | None = None
    date_start: date | None = None
    date_end: date | None = None
    owner_user_id: UUID | None = None

    @model_validator(mode="after")
    def changes_required(self) -> ProgramPatch:
        changes = self.model_fields_set - {"expected_version"}
        if not changes or any(
            getattr(self, field) is None for field in changes - {"owner_user_id"}
        ):
            raise ValueError("provide non-null audit program changes")
        return self


class ProgramTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_state: ProgramState
    decision: Decision


class ProgramResponse(ProgramInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    state: str
    cancellation_reason: str
    row_version: int
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class InternalAuditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    program_id: UUID | None = None
    code: Code
    name: Name
    audit_type: AuditType = "process"
    planned_start: date
    planned_end: date
    objective: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    scope_summary: Narrative = ""
    conclusion: Narrative = ""
    lead_auditor_user_id: UUID | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> InternalAuditInput:
        if self.planned_end < self.planned_start:
            raise ValueError("audit end date cannot precede its start date")
        return self


class InternalAuditPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    program_id: UUID | None = None
    name: Name | None = None
    audit_type: AuditType | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    objective: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ] = None
    scope_summary: Narrative | None = None
    conclusion: Narrative | None = None
    lead_auditor_user_id: UUID | None = None

    @model_validator(mode="after")
    def changes_required(self) -> InternalAuditPatch:
        changes = self.model_fields_set - {"expected_version"}
        nullable = {"program_id", "lead_auditor_user_id"}
        if not changes or any(getattr(self, field) is None for field in changes - nullable):
            raise ValueError("provide non-null internal audit changes")
        return self


class InternalAuditTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_state: AuditPlanningState
    decision: Decision


class InternalAuditResponse(InternalAuditInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    actual_start: date | None
    actual_end: date | None
    independence_status: str
    independence_notes: str
    independence_reviewed_by_user_id: UUID | None
    independence_reviewed_at: datetime | None
    state: str
    cancellation_reason: str
    row_version: int
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _program_values(row: QMSAuditProgram) -> dict[str, object]:
    values = {
        field: _value(getattr(row, field))
        for field in [
            "unit_id",
            "code",
            "date_start",
            "date_end",
            "owner_user_id",
            "state",
            "approved_by_user_id",
            "approved_at",
            "completed_by_user_id",
            "completed_at",
            "cancelled_by_user_id",
            "cancelled_at",
            "row_version",
        ]
    }
    values.update(
        name_hash=_hash(row.name),
        objective_hash=_hash(row.objective),
        description_hash=_hash(row.description),
        cancellation_reason_hash=_hash(row.cancellation_reason),
    )
    return values


def _audit_values(row: QMSInternalAudit) -> dict[str, object]:
    values = {
        field: _value(getattr(row, field))
        for field in [
            "unit_id",
            "program_id",
            "code",
            "audit_type",
            "planned_start",
            "planned_end",
            "actual_start",
            "actual_end",
            "lead_auditor_user_id",
            "independence_status",
            "independence_reviewed_by_user_id",
            "independence_reviewed_at",
            "state",
            "completed_by_user_id",
            "completed_at",
            "cancelled_by_user_id",
            "cancelled_at",
            "row_version",
        ]
    }
    values.update(
        name_hash=_hash(row.name),
        objective_hash=_hash(row.objective),
        scope_summary_hash=_hash(row.scope_summary),
        conclusion_hash=_hash(row.conclusion),
        independence_notes_hash=_hash(row.independence_notes),
        cancellation_reason_hash=_hash(row.cancellation_reason),
    )
    return values


def _record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSAuditProgram | QMSInternalAudit,
    action: str,
    before: dict[str, object] | None,
    decision: str | None = None,
) -> None:
    after = _program_values(row) if isinstance(row, QMSAuditProgram) else _audit_values(row)
    if decision is not None:
        after["decision"] = decision
    audit_service.record_internal_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=row.id,
        request_id=request_id,
        old_values=before,
        new_values=after,
    )


def _db_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    detail = error.orig.args[0] if error.orig is not None and error.orig.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(
            409, "internal-audit scope, member, state or version conflicts"
        ) from None
    if state == "42501":
        raise HTTPException(403, "internal-audit authority denied") from None
    raise error


def _program(
    db: Session, actor: OrganizationActor, program_id: UUID, *, lock: bool = False
) -> QMSAuditProgram:
    query = select(QMSAuditProgram).where(
        QMSAuditProgram.id == program_id, QMSAuditProgram.tenant_id == actor.tenant_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "audit program not found")
    require_capability(db, "audits.read", row.unit_id)
    return row


def _audit(
    db: Session, actor: OrganizationActor, audit_id: UUID, *, lock: bool = False
) -> QMSInternalAudit:
    query = select(QMSInternalAudit).where(
        QMSInternalAudit.id == audit_id, QMSInternalAudit.tenant_id == actor.tenant_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "internal audit not found")
    require_capability(db, "audits.read", row.unit_id)
    return row


@router.get("/programs", response_model=list[ProgramResponse])
def list_programs(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditProgram]:
    actor = actor_context(db, authenticated)
    require_capability(db, "audits.read", unit_id)
    query = select(QMSAuditProgram).where(
        QMSAuditProgram.tenant_id == actor.tenant_id, QMSAuditProgram.unit_id == unit_id
    )
    if q and q.strip():
        literal = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                QMSAuditProgram.code.ilike(f"%{literal}%", escape="\\"),
                QMSAuditProgram.name.ilike(f"%{literal}%", escape="\\"),
            )
        )
    return list(
        db.scalars(
            query.order_by(QMSAuditProgram.date_start.desc(), QMSAuditProgram.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/programs",
    response_model=ProgramResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_program(
    request: Request, body: ProgramInput, db: DBSession, authenticated: Authenticated
) -> QMSAuditProgram:
    actor = actor_context(db, authenticated)
    require_capability(db, "audits.read", body.unit_id)
    require_capability(db, "audits.manage", body.unit_id)
    now = datetime.now(UTC)
    row = QMSAuditProgram(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        state="draft",
        cancellation_reason="",
        row_version=1,
        approved_by_user_id=None,
        approved_at=None,
        completed_by_user_id=None,
        completed_at=None,
        cancelled_by_user_id=None,
        cancelled_at=None,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _record(db, actor, request.state.request_id, row, "audit_program.created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/programs/{program_id}", response_model=ProgramResponse)
def get_program(program_id: UUID, db: DBSession, authenticated: Authenticated) -> QMSAuditProgram:
    return _program(db, actor_context(db, authenticated), program_id)


@router.patch(
    "/programs/{program_id}", response_model=ProgramResponse, dependencies=[Depends(require_csrf)]
)
def update_program(
    request: Request,
    program_id: UUID,
    body: ProgramPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSAuditProgram:
    actor = actor_context(db, authenticated)
    row = _program(db, actor, program_id, lock=True)
    require_capability(db, "audits.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "audit program changed; refresh before editing")
    if row.state in {"completed", "cancelled"}:
        raise HTTPException(409, "terminated audit programs are immutable")
    before = _program_values(row)
    for key, value in body.model_dump(exclude={"expected_version"}, exclude_unset=True).items():
        setattr(row, key, value)
    if row.date_end < row.date_start:
        raise HTTPException(422, "audit program end date cannot precede its start date")
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _record(db, actor, request.state.request_id, row, "audit_program.updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/programs/{program_id}/transition",
    response_model=ProgramResponse,
    dependencies=[Depends(require_csrf)],
)
def transition_program(
    request: Request,
    program_id: UUID,
    body: ProgramTransition,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSAuditProgram:
    actor = actor_context(db, authenticated)
    row = _program(db, actor, program_id, lock=True)
    require_capability(db, "audits.review", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "audit program changed; refresh before reviewing")
    allowed = {
        "draft": {"approved", "cancelled"},
        "approved": {"active", "cancelled"},
        "active": {"completed", "cancelled"},
    }
    if body.target_state not in allowed.get(row.state, set()):
        raise HTTPException(409, "invalid audit program transition")
    before = _program_values(row)
    now = datetime.now(UTC)
    if body.target_state == "approved":
        row.approved_by_user_id, row.approved_at = actor.user_id, now
    if body.target_state == "completed":
        row.completed_by_user_id, row.completed_at = actor.user_id, now
    if body.target_state == "cancelled":
        row.cancelled_by_user_id, row.cancelled_at, row.cancellation_reason = (
            actor.user_id,
            now,
            body.decision,
        )
    row.state = body.target_state
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.audit_program_workflow','transition',true)"))
        db.flush()
        _record(
            db,
            actor,
            request.state.request_id,
            row,
            "audit_program.transitioned",
            before,
            body.decision,
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/audits", response_model=list[InternalAuditResponse])
def list_audits(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSInternalAudit]:
    actor = actor_context(db, authenticated)
    require_capability(db, "audits.read", unit_id)
    return list(
        db.scalars(
            select(QMSInternalAudit)
            .where(
                QMSInternalAudit.tenant_id == actor.tenant_id, QMSInternalAudit.unit_id == unit_id
            )
            .order_by(QMSInternalAudit.planned_start.desc(), QMSInternalAudit.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/audits",
    response_model=InternalAuditResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_audit(
    request: Request, body: InternalAuditInput, db: DBSession, authenticated: Authenticated
) -> QMSInternalAudit:
    actor = actor_context(db, authenticated)
    require_capability(db, "audits.read", body.unit_id)
    require_capability(db, "audits.manage", body.unit_id)
    now = datetime.now(UTC)
    row = QMSInternalAudit(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        actual_start=None,
        actual_end=None,
        independence_status="pending",
        independence_notes="",
        independence_reviewed_by_user_id=None,
        independence_reviewed_at=None,
        state="draft",
        cancellation_reason="",
        row_version=1,
        completed_by_user_id=None,
        completed_at=None,
        cancelled_by_user_id=None,
        cancelled_at=None,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _record(db, actor, request.state.request_id, row, "internal_audit.created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/audits/{audit_id}", response_model=InternalAuditResponse)
def get_audit(audit_id: UUID, db: DBSession, authenticated: Authenticated) -> QMSInternalAudit:
    return _audit(db, actor_context(db, authenticated), audit_id)


@router.patch(
    "/audits/{audit_id}", response_model=InternalAuditResponse, dependencies=[Depends(require_csrf)]
)
def update_audit(
    request: Request,
    audit_id: UUID,
    body: InternalAuditPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSInternalAudit:
    actor = actor_context(db, authenticated)
    row = _audit(db, actor, audit_id, lock=True)
    require_capability(db, "audits.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "internal audit changed; refresh before editing")
    if row.state in {"completed", "cancelled"}:
        raise HTTPException(409, "terminated internal audits are immutable")
    before = _audit_values(row)
    for key, value in body.model_dump(exclude={"expected_version"}, exclude_unset=True).items():
        setattr(row, key, value)
    if row.planned_end < row.planned_start:
        raise HTTPException(422, "audit end date cannot precede its start date")
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _record(db, actor, request.state.request_id, row, "internal_audit.updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/audits/{audit_id}/transition",
    response_model=InternalAuditResponse,
    dependencies=[Depends(require_csrf)],
)
def transition_audit(
    request: Request,
    audit_id: UUID,
    body: InternalAuditTransition,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSInternalAudit:
    actor = actor_context(db, authenticated)
    row = _audit(db, actor, audit_id, lock=True)
    capability = (
        "audits.manage"
        if row.state == "draft" and body.target_state == "planned"
        else "audits.review"
    )
    require_capability(db, capability, row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "internal audit changed; refresh before transition")
    allowed = {"draft": {"planned", "cancelled"}, "planned": {"cancelled"}}
    if body.target_state not in allowed.get(row.state, set()):
        raise HTTPException(409, "transition belongs to the execution slice")
    before = _audit_values(row)
    now = datetime.now(UTC)
    if body.target_state == "cancelled":
        row.cancelled_by_user_id, row.cancelled_at, row.cancellation_reason = (
            actor.user_id,
            now,
            body.decision,
        )
    row.state = body.target_state
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.internal_audit_workflow','transition',true)"))
        db.flush()
        _record(
            db,
            actor,
            request.state.request_id,
            row,
            "internal_audit.transitioned",
            before,
            body.decision,
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row
