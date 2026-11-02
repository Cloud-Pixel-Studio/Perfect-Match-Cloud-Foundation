"""Tenant-scoped risks and opportunities with a controlled review lifecycle."""

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
from pmc_api.models import QMSRisk
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/risks", tags=["risks"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Narrative = Annotated[str, StringConstraints(max_length=4000)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
RiskType = Annotated[str, StringConstraints(pattern="^(risk|opportunity)$")]
Category = Annotated[
    str,
    StringConstraints(
        pattern="^(strategic|operational|process|supplier|document|customer|security|other)$"
    ),
]
Strategy = Annotated[
    str, StringConstraints(pattern="^(accept|mitigate|transfer|avoid|exploit|enhance|share)$")
]
State = Annotated[
    str, StringConstraints(pattern="^(draft|assessed|action_required|monitoring|closed)$")
]
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]


class RiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    process_id: UUID
    code: Code
    name: Name
    risk_type: RiskType = "risk"
    category: Category = "operational"
    source: Annotated[str, StringConstraints(max_length=200)] = ""
    description: Description
    cause: Narrative = ""
    potential_effect: Narrative = ""
    benefit: Narrative = ""
    opportunity_action: Narrative = ""
    mitigation_plan: Narrative = ""
    closure_notes: Narrative = ""
    owner_user_id: UUID | None = None
    likelihood: Rating = 1
    impact: Rating = 1
    residual_likelihood: Rating = 1
    residual_impact: Rating = 1
    response_strategy: Strategy = "mitigate"
    target_date: date | None = None
    review_date: date | None = None


class RiskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: Name | None = None
    risk_type: RiskType | None = None
    category: Category | None = None
    source: Annotated[str, StringConstraints(max_length=200)] | None = None
    description: Description | None = None
    cause: Narrative | None = None
    potential_effect: Narrative | None = None
    benefit: Narrative | None = None
    opportunity_action: Narrative | None = None
    mitigation_plan: Narrative | None = None
    closure_notes: Narrative | None = None
    owner_user_id: UUID | None = None
    likelihood: Rating | None = None
    impact: Rating | None = None
    residual_likelihood: Rating | None = None
    residual_impact: Rating | None = None
    response_strategy: Strategy | None = None
    target_date: date | None = None
    review_date: date | None = None

    @model_validator(mode="after")
    def non_null_changes(self) -> RiskPatch:
        changes = self.model_fields_set - {"expected_version"}
        if not changes or any(
            getattr(self, field) is None
            for field in changes - {"owner_user_id", "target_date", "review_date"}
        ):
            raise ValueError("provide non-null risk changes")
        return self


class RiskTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_state: State
    decision: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    closure_notes: Narrative | None = None

    @model_validator(mode="after")
    def closure_only_on_close(self) -> RiskTransition:
        if self.closure_notes is not None and self.target_state != "closed":
            raise ValueError("closure notes belong to a closure command")
        return self


class RiskResponse(RiskInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    state: str
    scoring_model: str
    threshold_moderate: int
    threshold_high: int
    threshold_critical: int
    assessed_by_user_id: UUID | None
    assessed_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    def _level(self, score: int) -> str:
        if score >= self.threshold_critical:
            return "critical"
        if score >= self.threshold_high:
            return "high"
        if score >= self.threshold_moderate:
            return "moderate"
        return "low"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def initial_score(self) -> int:
        return self.likelihood * self.impact

    @computed_field  # type: ignore[prop-decorator]
    @property
    def residual_score(self) -> int:
        return self.residual_likelihood * self.residual_impact

    @computed_field  # type: ignore[prop-decorator]
    @property
    def initial_level(self) -> str:
        return self._level(self.initial_score)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def residual_level(self) -> str:
        return self._level(self.residual_score)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_overdue(self) -> int:
        if self.state == "closed" or self.target_date is None:
            return 0
        return max(0, (datetime.now(UTC).date() - self.target_date).days)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0


def _audit_values(row: QMSRisk) -> dict[str, object]:
    fields = (
        "unit_id process_id code name risk_type category owner_user_id likelihood impact "
        "residual_likelihood residual_impact response_strategy target_date review_date state "
        "scoring_model threshold_moderate threshold_high threshold_critical assessed_by_user_id "
        "assessed_at reviewed_by_user_id reviewed_at closed_by_user_id closed_at row_version"
    )
    values: dict[str, object] = {}
    for field in fields.split():
        value = getattr(row, field)
        values[field] = (
            value.isoformat()
            if isinstance(value, (date, datetime))
            else (str(value) if isinstance(value, UUID) else value)
        )
    for field in (
        "source",
        "description",
        "cause",
        "potential_effect",
        "benefit",
        "opportunity_action",
        "mitigation_plan",
        "closure_notes",
    ):
        values[f"{field}_hash"] = hashlib.sha256(getattr(row, field).encode()).hexdigest()
    return values


def _record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSRisk,
    action: str,
    before: dict[str, object] | None,
    decision: str | None = None,
) -> None:
    after = _audit_values(row)
    if decision is not None:
        after["decision"] = decision
    audit_service.record_risk(
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
        raise HTTPException(409, "risk scope, owner, state or version conflicts") from None
    if state == "42501":
        raise HTTPException(403, "risk authority denied") from None
    raise error


def _row(db: Session, actor: OrganizationActor, risk_id: UUID, *, lock: bool = False) -> QMSRisk:
    query = select(QMSRisk).where(QMSRisk.id == risk_id, QMSRisk.tenant_id == actor.tenant_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "risk not found")
    require_capability(db, "risks.read", row.unit_id)
    return row


def create_risk(
    db: Session, actor: OrganizationActor, request_id: UUID, body: RiskInput
) -> QMSRisk:
    require_capability(db, "risks.manage", body.unit_id)
    require_capability(db, "processes.read", body.unit_id)
    now = datetime.now(UTC)
    row = QMSRisk(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        state="draft",
        scoring_model="PMC-RISK-5X5-v1",
        threshold_moderate=5,
        threshold_high=10,
        threshold_critical=16,
        assessed_by_user_id=None,
        assessed_at=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
        closed_by_user_id=None,
        closed_at=None,
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _record(db, actor, request_id, row, "risk.created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def update_risk(
    db: Session, actor: OrganizationActor, request_id: UUID, risk_id: UUID, body: RiskPatch
) -> QMSRisk:
    row = _row(db, actor, risk_id, lock=True)
    require_capability(db, "risks.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "risk changed; refresh before editing")
    if row.state == "closed":
        raise HTTPException(409, "closed risks are immutable")
    before = _audit_values(row)
    for key, value in body.model_dump(exclude={"expected_version"}, exclude_unset=True).items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _record(db, actor, request_id, row, "risk.updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def transition_risk(
    db: Session, actor: OrganizationActor, request_id: UUID, risk_id: UUID, body: RiskTransition
) -> QMSRisk:
    row = _row(db, actor, risk_id, lock=True)
    require_capability(db, "risks.review", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "risk changed; refresh before reviewing")
    allowed = {
        "draft": {"assessed"},
        "assessed": {"action_required", "monitoring"},
        "action_required": {"monitoring"},
        "monitoring": {"action_required", "monitoring", "closed"},
        "closed": set(),
    }
    if body.target_state not in allowed.get(row.state, set()):
        raise HTTPException(409, "invalid risk transition")
    if (
        body.target_state == "closed"
        and not (
            body.closure_notes if body.closure_notes is not None else row.closure_notes
        ).strip()
    ):
        raise HTTPException(422, "closure notes are required")
    before = _audit_values(row)
    review = row.state == body.target_state
    now = datetime.now(UTC)
    if body.closure_notes is not None:
        row.closure_notes = body.closure_notes
    if row.state == "draft":
        row.assessed_by_user_id, row.assessed_at = actor.user_id, now
    else:
        row.reviewed_by_user_id, row.reviewed_at = actor.user_id, now
    if body.target_state == "closed":
        row.closed_by_user_id, row.closed_at = actor.user_id, now
    row.state = body.target_state
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(
            text("SELECT set_config('app.risk_workflow', :command, true)"),
            {"command": "review" if review else "transition"},
        )
        db.flush()
        _record(
            db,
            actor,
            request_id,
            row,
            "risk.reviewed" if review else "risk.transitioned",
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


@router.get("", response_model=list[RiskResponse])
def list_risks(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    q: Annotated[str | None, Query(max_length=160)] = None,
    state: State | None = None,
    risk_type: RiskType | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSRisk]:
    actor = actor_context(db, authenticated)
    require_capability(db, "risks.read", unit_id)
    query = select(QMSRisk).where(QMSRisk.tenant_id == actor.tenant_id, QMSRisk.unit_id == unit_id)
    if q:
        literal = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                QMSRisk.code.ilike(f"%{literal}%", escape="\\"),
                QMSRisk.name.ilike(f"%{literal}%", escape="\\"),
            )
        )
    if state:
        query = query.where(QMSRisk.state == state)
    if risk_type:
        query = query.where(QMSRisk.risk_type == risk_type)
    return list(db.scalars(query.order_by(QMSRisk.code, QMSRisk.id).limit(limit).offset(offset)))


@router.get("/{risk_id}", response_model=RiskResponse)
def get_risk(db: DBSession, authenticated: Authenticated, risk_id: UUID) -> QMSRisk:
    return _row(db, actor_context(db, authenticated), risk_id)


@router.post("", response_model=RiskResponse, status_code=201, dependencies=[Depends(require_csrf)])
def create(
    request: Request, body: RiskInput, db: DBSession, authenticated: Authenticated
) -> QMSRisk:
    return create_risk(db, actor_context(db, authenticated), request.state.request_id, body)


@router.patch("/{risk_id}", response_model=RiskResponse, dependencies=[Depends(require_csrf)])
def update(
    request: Request, risk_id: UUID, body: RiskPatch, db: DBSession, authenticated: Authenticated
) -> QMSRisk:
    return update_risk(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, body
    )


@router.post(
    "/{risk_id}/transition", response_model=RiskResponse, dependencies=[Depends(require_csrf)]
)
def transition(
    request: Request,
    risk_id: UUID,
    body: RiskTransition,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSRisk:
    return transition_risk(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, body
    )
