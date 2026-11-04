"""Tenant-scoped nonconformity intake, containment and controlled closure."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)
from sqlalchemy import or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import QMSNonconformity
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/nonconformities", tags=["nonconformities"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Narrative = Annotated[str, StringConstraints(max_length=4000)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
Source = Annotated[
    str,
    StringConstraints(
        pattern="^(internal|customer|supplier|process|product|document|audit|other)$"
    ),
]
Severity = Annotated[str, StringConstraints(pattern="^(minor|major|critical)$")]
Disposition = Annotated[
    str,
    StringConstraints(pattern="^(use_as_is|rework|repair|return|scrap|information_only|other)$"),
]
State = Annotated[
    str,
    StringConstraints(
        pattern="^(draft|open|containment|investigation|action_required|verification|closed|cancelled)$"
    ),
]


class NCRInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    process_id: UUID
    code: Code
    name: Name
    source_type: Source = "internal"
    severity: Severity = "minor"
    description: Description
    detected_date: date = Field(default_factory=lambda: datetime.now(UTC).date())
    owner_user_id: UUID | None = None
    containment_required: bool = False
    containment_action: Narrative = ""
    containment_owner_user_id: UUID | None = None
    containment_date: date | None = None
    containment_completed: bool = False
    disposition: Disposition | None = None
    disposition_notes: Narrative = ""
    root_cause_summary: Narrative = ""
    closure_notes: Narrative = ""
    target_date: date | None = None

    @model_validator(mode="after")
    def completion_metadata(self) -> NCRInput:
        if self.containment_completed and (
            not self.containment_action.strip() or self.containment_date is None
        ):
            raise ValueError("completed containment requires an action and date")
        return self


class NCRPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: Name | None = None
    source_type: Source | None = None
    severity: Severity | None = None
    description: Description | None = None
    detected_date: date | None = None
    owner_user_id: UUID | None = None
    containment_required: bool | None = None
    containment_action: Narrative | None = None
    containment_owner_user_id: UUID | None = None
    containment_date: date | None = None
    containment_completed: bool | None = None
    disposition: Disposition | None = None
    disposition_notes: Narrative | None = None
    root_cause_summary: Narrative | None = None
    closure_notes: Narrative | None = None
    target_date: date | None = None

    @model_validator(mode="after")
    def non_null_changes(self) -> NCRPatch:
        changes = self.model_fields_set - {"expected_version"}
        nullable = {
            "owner_user_id",
            "containment_owner_user_id",
            "containment_date",
            "disposition",
            "target_date",
        }
        if not changes or any(getattr(self, field) is None for field in changes - nullable):
            raise ValueError("provide non-null nonconformity changes")
        return self


class NCRTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_state: State
    decision: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    closure_notes: Narrative | None = None

    @model_validator(mode="after")
    def closure_only_on_close(self) -> NCRTransition:
        if self.closure_notes is not None and self.target_state != "closed":
            raise ValueError("closure notes belong to a closure command")
        return self


class NCRResponse(NCRInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    detected_by_user_id: UUID
    state: str
    cancellation_reason: str
    opened_by_user_id: UUID | None
    opened_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_overdue(self) -> int:
        if self.state in {"closed", "cancelled"} or self.target_date is None:
            return 0
        return max(0, (datetime.now(UTC).date() - self.target_date).days)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0


def _audit_values(row: QMSNonconformity) -> dict[str, object]:
    values: dict[str, object] = {}
    fields = (
        "unit_id process_id code name source_type severity detected_date detected_by_user_id "
        "owner_user_id containment_required containment_owner_user_id containment_date "
        "containment_completed disposition target_date state opened_by_user_id opened_at "
        "reviewed_by_user_id reviewed_at closed_by_user_id closed_at cancelled_by_user_id "
        "cancelled_at row_version"
    )
    for name in fields.split():
        value = getattr(row, name)
        values[name] = (
            str(value)
            if isinstance(value, UUID)
            else (value.isoformat() if isinstance(value, (date, datetime)) else value)
        )
    for name in (
        "description",
        "containment_action",
        "disposition_notes",
        "root_cause_summary",
        "closure_notes",
        "cancellation_reason",
    ):
        values[f"{name}_hash"] = hashlib.sha256(getattr(row, name).encode()).hexdigest()
    return values


def _record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSNonconformity,
    action: str,
    before: dict[str, object] | None,
    decision: str | None = None,
) -> None:
    after = _audit_values(row)
    if decision is not None:
        after["decision"] = decision
    audit_service.record_ncr(
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
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(
            409, "nonconformity scope, assignee, containment, state or version conflicts"
        ) from None
    if state == "42501":
        raise HTTPException(403, "nonconformity authority denied") from None
    raise error


def _row(
    db: Session, actor: OrganizationActor, ncr_id: UUID, *, lock: bool = False
) -> QMSNonconformity:
    query = select(QMSNonconformity).where(
        QMSNonconformity.id == ncr_id, QMSNonconformity.tenant_id == actor.tenant_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "nonconformity not found")
    require_capability(db, "ncr.read", row.unit_id)
    return row


def create_ncr(
    db: Session, actor: OrganizationActor, request_id: UUID, body: NCRInput
) -> QMSNonconformity:
    require_capability(db, "ncr.manage", body.unit_id)
    require_capability(db, "processes.read", body.unit_id)
    now = datetime.now(UTC)
    row = QMSNonconformity(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        detected_by_user_id=actor.user_id,
        state="draft",
        cancellation_reason="",
        opened_by_user_id=None,
        opened_at=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
        closed_by_user_id=None,
        closed_at=None,
        cancelled_by_user_id=None,
        cancelled_at=None,
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _record(db, actor, request_id, row, "ncr.created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def update_ncr(
    db: Session, actor: OrganizationActor, request_id: UUID, ncr_id: UUID, body: NCRPatch
) -> QMSNonconformity:
    row = _row(db, actor, ncr_id, lock=True)
    require_capability(db, "ncr.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "nonconformity changed; refresh before editing")
    if row.state in {"closed", "cancelled"}:
        raise HTTPException(409, "closed or cancelled nonconformities are immutable")
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if (
        row.state != "draft"
        and row.containment_required
        and changes.get("containment_required") is False
    ):
        raise HTTPException(409, "required containment cannot be waived after opening")
    if changes.get("containment_completed", row.containment_completed) and (
        not str(changes.get("containment_action", row.containment_action)).strip()
        or changes.get("containment_date", row.containment_date) is None
    ):
        raise HTTPException(422, "completed containment requires an action and date")
    before = _audit_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _record(db, actor, request_id, row, "ncr.updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def transition_ncr(
    db: Session, actor: OrganizationActor, request_id: UUID, ncr_id: UUID, body: NCRTransition
) -> QMSNonconformity:
    row = _row(db, actor, ncr_id, lock=True)
    opening = row.state == "draft" and body.target_state == "open"
    require_capability(db, "ncr.manage" if opening else "ncr.review", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "nonconformity changed; refresh before reviewing")
    allowed = {
        "draft": {"open", "cancelled"},
        "open": {"containment", "investigation", "cancelled"},
        "containment": {"investigation", "cancelled"},
        "investigation": {"action_required", "cancelled"},
        "action_required": {"verification", "closed", "cancelled"},
        "verification": {"closed", "cancelled"},
        "closed": set(),
        "cancelled": set(),
    }
    if body.target_state not in allowed.get(row.state, set()):
        raise HTTPException(409, "invalid nonconformity transition")
    if body.target_state == "containment" and not row.containment_required:
        raise HTTPException(409, "containment is not required for this record")
    if (
        body.target_state in {"investigation", "closed"}
        and row.containment_required
        and not row.containment_completed
    ):
        raise HTTPException(409, "complete required containment before investigation or closure")
    if (
        body.target_state == "closed"
        and not (
            body.closure_notes if body.closure_notes is not None else row.closure_notes
        ).strip()
    ):
        raise HTTPException(422, "closure notes are required")
    before = _audit_values(row)
    now = datetime.now(UTC)
    if opening:
        row.opened_by_user_id, row.opened_at = actor.user_id, now
    else:
        row.reviewed_by_user_id, row.reviewed_at = actor.user_id, now
    if body.target_state == "closed":
        row.closed_by_user_id, row.closed_at = actor.user_id, now
        if body.closure_notes is not None:
            row.closure_notes = body.closure_notes
    if body.target_state == "cancelled":
        row.cancelled_by_user_id, row.cancelled_at = actor.user_id, now
        row.cancellation_reason = body.decision
    row.state = body.target_state
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.ncr_workflow','transition',true)"))
        db.flush()
        _record(db, actor, request_id, row, "ncr.transitioned", before, body.decision)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("", response_model=list[NCRResponse])
def list_ncrs(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    q: Annotated[str | None, Query(max_length=160)] = None,
    state: State | None = None,
    source_type: Source | None = None,
    severity: Severity | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSNonconformity]:
    actor = actor_context(db, authenticated)
    require_capability(db, "ncr.read", unit_id)
    query = select(QMSNonconformity).where(
        QMSNonconformity.tenant_id == actor.tenant_id, QMSNonconformity.unit_id == unit_id
    )
    if q and q.strip():
        literal = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                QMSNonconformity.code.ilike(f"%{literal}%", escape="\\"),
                QMSNonconformity.name.ilike(f"%{literal}%", escape="\\"),
            )
        )
    if state:
        query = query.where(QMSNonconformity.state == state)
    if source_type:
        query = query.where(QMSNonconformity.source_type == source_type)
    if severity:
        query = query.where(QMSNonconformity.severity == severity)
    return list(
        db.scalars(
            query.order_by(QMSNonconformity.code, QMSNonconformity.id).limit(limit).offset(offset)
        )
    )


@router.get("/{ncr_id}", response_model=NCRResponse)
def get_ncr(db: DBSession, authenticated: Authenticated, ncr_id: UUID) -> QMSNonconformity:
    return _row(db, actor_context(db, authenticated), ncr_id)


@router.post("", response_model=NCRResponse, status_code=201, dependencies=[Depends(require_csrf)])
def create(
    request: Request, body: NCRInput, db: DBSession, authenticated: Authenticated
) -> QMSNonconformity:
    return create_ncr(db, actor_context(db, authenticated), request.state.request_id, body)


@router.patch("/{ncr_id}", response_model=NCRResponse, dependencies=[Depends(require_csrf)])
def update(
    request: Request, ncr_id: UUID, body: NCRPatch, db: DBSession, authenticated: Authenticated
) -> QMSNonconformity:
    return update_ncr(db, actor_context(db, authenticated), request.state.request_id, ncr_id, body)


@router.post(
    "/{ncr_id}/transition", response_model=NCRResponse, dependencies=[Depends(require_csrf)]
)
def transition(
    request: Request, ncr_id: UUID, body: NCRTransition, db: DBSession, authenticated: Authenticated
) -> QMSNonconformity:
    return transition_ncr(
        db, actor_context(db, authenticated), request.state.request_id, ncr_id, body
    )
