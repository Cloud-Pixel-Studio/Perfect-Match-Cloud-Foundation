"""CAPA intake and controlled root-cause analysis with tenant-scoped provenance."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import (
    QMSCAPA,
    QMSCAPAAction,
    QMSCAPAEffectivenessReview,
    QMSNonconformity,
    QMSRisk,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/capas", tags=["capa"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Problem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Source = Annotated[str, StringConstraints(pattern="^(ncr|risk|other)$")]
Method = Annotated[str, StringConstraints(pattern="^(5why|fishbone|is_is_not|other)$")]


class CAPAInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    process_id: UUID
    code: Code
    name: Name
    source_type: Source
    source_ncr_id: UUID | None = None
    source_risk_id: UUID | None = None
    source_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    problem_statement: Problem
    owner_user_id: UUID | None = None
    target_date: date | None = None
    root_cause_method: Method | None = None

    @model_validator(mode="after")
    def exact_source(self) -> CAPAInput:
        valid = (
            (
                self.source_type == "ncr"
                and self.source_ncr_id is not None
                and self.source_risk_id is None
            )
            or (
                self.source_type == "risk"
                and self.source_risk_id is not None
                and self.source_ncr_id is None
            )
            or (
                self.source_type == "other"
                and self.source_ncr_id is None
                and self.source_risk_id is None
            )
        )
        if not valid:
            raise ValueError("CAPA source requires exactly its matching reference")
        return self


class CAPAPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: Name | None = None
    problem_statement: Problem | None = None
    owner_user_id: UUID | None = None
    target_date: date | None = None
    root_cause_method: Method | None = None
    source_reference: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None
    ) = None

    @model_validator(mode="after")
    def changes_required(self) -> CAPAPatch:
        fields = self.model_fields_set - {"expected_version"}
        if not fields or any(
            getattr(self, field) is None
            for field in fields - {"owner_user_id", "target_date", "root_cause_method"}
        ):
            raise ValueError("provide valid CAPA changes")
        return self


class CAPAResponse(CAPAInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    source_code: str
    source_state: str
    source_reference: str
    analysis_data: dict[str, object]
    analysis_summary: str
    verified_root_cause: str
    other_method_name: str
    analysis_started_by_user_id: UUID | None
    analysis_started_at: datetime | None
    plan_summary: str
    planned_by_user_id: UUID | None
    planned_at: datetime | None
    implementation_started_by_user_id: UUID | None
    implementation_started_at: datetime | None
    review_started_by_user_id: UUID | None
    review_started_at: datetime | None
    effective_by_user_id: UUID | None
    effective_at: datetime | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    closure_notes: str
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str
    state: str
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class CAPAStartAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class CAPAAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    analysis_data: dict[str, object]
    analysis_summary: Annotated[str, StringConstraints(max_length=4000)] = ""
    verified_root_cause: Annotated[str, StringConstraints(max_length=4000)] = ""
    other_method_name: Annotated[str, StringConstraints(max_length=160)] = ""


class CAPAStartPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    plan_summary: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class CAPAActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_capa_version: int = Field(ge=1)
    title: Name
    description: Problem
    owner_user_id: UUID
    due_date: date


class CAPAActionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_capa_version: int = Field(ge=1)
    expected_action_version: int = Field(ge=1)
    title: Name | None = None
    description: Problem | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def changes_required(self) -> CAPAActionPatch:
        fields = self.model_fields_set - {"expected_capa_version", "expected_action_version"}
        if not fields or any(getattr(self, field) is None for field in fields):
            raise ValueError("provide valid action changes")
        return self


class CAPAActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    capa_id: UUID
    title: str
    description: str
    owner_user_id: UUID
    due_date: date
    state: str
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    verification_notes: str
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class CAPAStartImplementation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class CAPAStartEffectivenessReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class CAPAEffectivenessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    decision: Annotated[str, StringConstraints(pattern="^(effective|ineffective)$")]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class CAPAClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    closure_notes: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class CAPACancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CAPAEffectivenessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    capa_id: UUID
    cycle_number: int
    decision: str
    notes: str
    reviewer_user_id: UUID
    reviewed_at: datetime
    implementation_started_by_user_id: UUID
    implementation_started_at: datetime
    review_started_by_user_id: UUID
    review_started_at: datetime
    active_action_count: int
    verified_action_count: int
    cancelled_action_count: int


class CAPAActionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_capa_version: int = Field(ge=1)
    expected_action_version: int = Field(ge=1)
    target_state: Annotated[
        str, StringConstraints(pattern="^(in_progress|completed|verified|cancelled)$")
    ]
    verification_notes: Annotated[str, StringConstraints(max_length=4000)] = ""
    cancellation_reason: Annotated[str, StringConstraints(max_length=500)] = ""

    @model_validator(mode="after")
    def reason_matches_transition(self) -> CAPAActionTransition:
        if self.target_state == "verified":
            valid = bool(self.verification_notes.strip()) and not self.cancellation_reason
        elif self.target_state == "cancelled":
            valid = bool(self.cancellation_reason.strip()) and not self.verification_notes
        else:
            valid = not self.verification_notes and not self.cancellation_reason
        if not valid:
            raise ValueError("notes must match action transition")
        return self


def _scaffold(method: str) -> dict[str, object]:
    if method == "5why":
        return {f"why{number}": "" for number in range(1, 6)}
    if method == "fishbone":
        return {
            key: []
            for key in ("people", "process", "equipment", "materials", "measurement", "environment")
        }
    if method == "is_is_not":
        return {
            key: {field: "" for field in ("observed", "not_observed", "distinction", "change")}
            for key in ("what", "where", "when", "extent")
        }
    return {}


def _valid_analysis(method: str, data: dict[str, object]) -> bool:
    if (
        set(data) != set(_scaffold(method))
        or len(json.dumps(data, ensure_ascii=False).encode()) > 100000
    ):
        return False
    if method == "fishbone":
        return all(
            isinstance(causes, list)
            and len(causes) <= 10
            and all(
                isinstance(cause, dict)
                and set(cause) == {"statement", "evidence", "rationale", "confirmed"}
                and all(
                    isinstance(cause.get(field), str) and len(cause[field]) <= maximum
                    for field, maximum in (
                        ("statement", 1000),
                        ("evidence", 2000),
                        ("rationale", 2000),
                    )
                )
                and bool(cause["statement"].strip())
                and type(cause.get("confirmed")) is bool
                and (
                    not cause["confirmed"]
                    or (bool(cause["evidence"].strip()) and bool(cause["rationale"].strip()))
                )
                for cause in causes
            )
            for causes in data.values()
        )
    if method == "is_is_not":
        return all(
            isinstance(value, dict)
            and set(value) == {"observed", "not_observed", "distinction", "change"}
            and all(isinstance(text, str) and len(text) <= 1000 for text in value.values())
            for value in data.values()
        )
    return all(isinstance(value, str) and len(value) <= 1000 for value in data.values())


def _analysis_ready(row: QMSCAPA) -> bool:
    method = row.root_cause_method
    data = row.analysis_data
    if not method or not _valid_analysis(method, data):
        return False
    if not row.analysis_summary.strip() or not row.verified_root_cause.strip():
        return False
    if method == "5why":
        seen_blank = False
        for number in range(1, 6):
            value = data.get(f"why{number}")
            if not isinstance(value, str):
                return False
            if not value.strip():
                seen_blank = True
            elif seen_blank:
                return False
        first = data.get("why1")
        return isinstance(first, str) and bool(first.strip())
    if method == "fishbone":
        return any(
            cause["confirmed"] is True
            for causes in data.values()
            if isinstance(causes, list)
            for cause in causes
        )
    if method == "is_is_not":
        return all(
            isinstance(value, dict)
            and all(
                isinstance(value.get(field), str) and value[field].strip()
                for field in ("observed", "not_observed", "distinction")
            )
            for value in data.values()
        )
    return bool(row.other_method_name.strip())


def _audit_values(row: QMSCAPA) -> dict[str, object]:
    fields = (
        "unit_id process_id code name source_type source_ncr_id source_risk_id "
        "source_code source_state owner_user_id target_date root_cause_method "
        "analysis_started_by_user_id analysis_started_at planned_by_user_id planned_at "
        "implementation_started_by_user_id implementation_started_at "
        "review_started_by_user_id review_started_at "
        "effective_by_user_id effective_at closed_by_user_id closed_at "
        "cancelled_by_user_id cancelled_at "
        "state row_version"
    )
    values: dict[str, object] = {}
    for field in fields.split():
        value = getattr(row, field)
        values[field] = (
            str(value)
            if isinstance(value, UUID)
            else (value.isoformat() if isinstance(value, date) else value)
        )
    values["problem_statement_hash"] = hashlib.sha256(row.problem_statement.encode()).hexdigest()
    values["source_reference_hash"] = hashlib.sha256(row.source_reference.encode()).hexdigest()
    values["analysis_data_hash"] = hashlib.sha256(
        json.dumps(row.analysis_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    for field in ("analysis_summary", "verified_root_cause", "other_method_name", "plan_summary"):
        values[f"{field}_hash"] = hashlib.sha256(getattr(row, field).encode()).hexdigest()
    values["closure_notes_hash"] = hashlib.sha256(row.closure_notes.encode()).hexdigest()
    values["cancellation_reason_hash"] = hashlib.sha256(
        row.cancellation_reason.encode()
    ).hexdigest()
    return values


def _record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSCAPA,
    action: str,
    before: dict[str, object] | None,
) -> None:
    audit_service.record_capa(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=row.id,
        request_id=request_id,
        old_values=before,
        new_values=_audit_values(row),
    )


def _action_values(row: QMSCAPAAction) -> dict[str, object]:
    return {
        "capa_id": str(row.capa_id),
        "unit_id": str(row.unit_id),
        "title_hash": hashlib.sha256(row.title.encode()).hexdigest(),
        "description_hash": hashlib.sha256(row.description.encode()).hexdigest(),
        "owner_user_id": str(row.owner_user_id),
        "due_date": row.due_date.isoformat(),
        "state": row.state,
        "completed_by_user_id": str(row.completed_by_user_id) if row.completed_by_user_id else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "verified_by_user_id": str(row.verified_by_user_id) if row.verified_by_user_id else None,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "verification_notes_hash": hashlib.sha256(row.verification_notes.encode()).hexdigest(),
        "cancelled_by_user_id": str(row.cancelled_by_user_id) if row.cancelled_by_user_id else None,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "cancellation_reason_hash": hashlib.sha256(row.cancellation_reason.encode()).hexdigest(),
        "row_version": row.row_version,
        "created_by_user_id": str(row.created_by_user_id),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _record_action(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSCAPAAction,
    action: str,
    before: dict[str, object] | None,
) -> None:
    audit_service.record_capa_action(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=row.id,
        request_id=request_id,
        old_values=before,
        new_values=_action_values(row),
    )


def _review_values(row: QMSCAPAEffectivenessReview) -> dict[str, object]:
    return {
        "capa_id": str(row.capa_id),
        "unit_id": str(row.unit_id),
        "cycle_number": row.cycle_number,
        "decision": row.decision,
        "notes_hash": hashlib.sha256(row.notes.encode()).hexdigest(),
        "reviewer_user_id": str(row.reviewer_user_id),
        "reviewed_at": row.reviewed_at.isoformat(),
        "implementation_started_by_user_id": str(row.implementation_started_by_user_id),
        "implementation_started_at": row.implementation_started_at.isoformat(),
        "review_started_by_user_id": str(row.review_started_by_user_id),
        "review_started_at": row.review_started_at.isoformat(),
        "active_action_count": row.active_action_count,
        "verified_action_count": row.verified_action_count,
        "cancelled_action_count": row.cancelled_action_count,
    }


def _record_review(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSCAPAEffectivenessReview,
) -> None:
    audit_service.record_capa_effectiveness_review(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action="capa.effectiveness_recorded",
        resource_id=row.id,
        request_id=request_id,
        old_values=None,
        new_values=_review_values(row),
    )


def _db_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(409, "CAPA origin, process, owner or version conflicts") from None
    if state == "42501":
        raise HTTPException(403, "CAPA authority denied") from None
    raise error


def _origin(db: Session, actor: OrganizationActor, body: CAPAInput) -> tuple[str, str]:
    if body.source_type == "other":
        return "", ""
    capability = "ncr.read" if body.source_type == "ncr" else "risks.read"
    require_capability(db, capability, body.unit_id)
    source: QMSNonconformity | QMSRisk | None
    if body.source_type == "ncr":
        source = db.scalar(
            select(QMSNonconformity).where(
                QMSNonconformity.id == body.source_ncr_id,
                QMSNonconformity.tenant_id == actor.tenant_id,
                QMSNonconformity.unit_id == body.unit_id,
            )
        )
    else:
        source = db.scalar(
            select(QMSRisk).where(
                QMSRisk.id == body.source_risk_id,
                QMSRisk.tenant_id == actor.tenant_id,
                QMSRisk.unit_id == body.unit_id,
            )
        )
    if source is None or source.state == "cancelled":
        raise HTTPException(404, "CAPA origin not found")
    return source.code, source.state


def _row(db: Session, actor: OrganizationActor, capa_id: UUID, *, lock: bool = False) -> QMSCAPA:
    query = select(QMSCAPA).where(QMSCAPA.id == capa_id, QMSCAPA.tenant_id == actor.tenant_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "CAPA not found")
    require_capability(db, "capa.read", row.unit_id)
    if row.source_type != "other":
        require_capability(
            db, "ncr.read" if row.source_type == "ncr" else "risks.read", row.unit_id
        )
    return row


@router.get("", response_model=list[CAPAResponse])
def list_capas(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    q: Annotated[str | None, Query(max_length=160)] = None,
    source_type: Source | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSCAPA]:
    actor = actor_context(db, authenticated)
    require_capability(db, "capa.read", unit_id)
    query = select(QMSCAPA).where(QMSCAPA.tenant_id == actor.tenant_id, QMSCAPA.unit_id == unit_id)
    if source_type:
        query = query.where(QMSCAPA.source_type == source_type)
    if q and q.strip():
        literal = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                QMSCAPA.code.ilike(f"%{literal}%", escape="\\"),
                QMSCAPA.name.ilike(f"%{literal}%", escape="\\"),
            )
        )
    return list(db.scalars(query.order_by(QMSCAPA.code, QMSCAPA.id).limit(limit).offset(offset)))


@router.get("/{capa_id}", response_model=CAPAResponse)
def get_capa(db: DBSession, authenticated: Authenticated, capa_id: UUID) -> QMSCAPA:
    return _row(db, actor_context(db, authenticated), capa_id)


@router.post("", response_model=CAPAResponse, status_code=201, dependencies=[Depends(require_csrf)])
def create_capa(
    request: Request, body: CAPAInput, db: DBSession, authenticated: Authenticated
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    require_capability(db, "capa.read", body.unit_id)
    require_capability(db, "capa.manage", body.unit_id)
    require_capability(db, "processes.read", body.unit_id)
    source_code, source_state = _origin(db, actor, body)
    now = datetime.now(UTC)
    row = QMSCAPA(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        source_code=source_code,
        source_state=source_state,
        analysis_data={},
        analysis_summary="",
        verified_root_cause="",
        other_method_name="",
        analysis_started_by_user_id=None,
        analysis_started_at=None,
        plan_summary="",
        planned_by_user_id=None,
        planned_at=None,
        implementation_started_by_user_id=None,
        implementation_started_at=None,
        review_started_by_user_id=None,
        review_started_at=None,
        effective_by_user_id=None,
        effective_at=None,
        closed_by_user_id=None,
        closed_at=None,
        closure_notes="",
        cancelled_by_user_id=None,
        cancelled_at=None,
        cancellation_reason="",
        state="draft",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.patch("/{capa_id}", response_model=CAPAResponse, dependencies=[Depends(require_csrf)])
def update_capa(
    request: Request, capa_id: UUID, body: CAPAPatch, db: DBSession, authenticated: Authenticated
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "CAPA changed; refresh before editing")
    if row.state not in {"draft", "analysis"}:
        raise HTTPException(409, "CAPA details are locked after planning starts")
    if row.state == "analysis" and "root_cause_method" in body.model_fields_set:
        raise HTTPException(409, "root cause method is locked after analysis starts")
    if row.state == "analysis" and "source_reference" in body.model_fields_set:
        raise HTTPException(409, "source reference is locked after analysis starts")
    before = _audit_values(row)
    for field, value in body.model_dump(exclude={"expected_version"}, exclude_unset=True).items():
        setattr(row, field, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','edit',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/analysis/start",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def start_analysis(
    request: Request,
    capa_id: UUID,
    body: CAPAStartAnalysis,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version or row.state != "draft":
        raise HTTPException(409, "CAPA draft changed; refresh before starting analysis")
    if row.root_cause_method is None:
        raise HTTPException(422, "choose a root cause method before analysis")
    before = _audit_values(row)
    now = datetime.now(UTC)
    row.state = "analysis"
    row.analysis_data = _scaffold(row.root_cause_method)
    row.analysis_started_by_user_id = actor.user_id
    row.analysis_started_at = now
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','start',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.analysis_started", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.patch(
    "/{capa_id}/analysis",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def update_analysis(
    request: Request,
    capa_id: UUID,
    body: CAPAAnalysisInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version or row.state != "analysis":
        raise HTTPException(409, "CAPA analysis changed; refresh before editing")
    if not row.root_cause_method or not _valid_analysis(row.root_cause_method, body.analysis_data):
        raise HTTPException(422, "analysis structure does not match the selected method")
    if row.root_cause_method != "other" and body.other_method_name:
        raise HTTPException(422, "method name only applies to the alternative method")
    before = _audit_values(row)
    row.analysis_data = body.analysis_data
    row.analysis_summary = body.analysis_summary
    row.verified_root_cause = body.verified_root_cause
    row.other_method_name = body.other_method_name
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','edit',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.analysis_updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/plan/start",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def start_plan(
    request: Request,
    capa_id: UUID,
    body: CAPAStartPlan,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version or row.state != "analysis":
        raise HTTPException(409, "CAPA analysis changed; refresh before planning")
    if not _analysis_ready(row):
        raise HTTPException(422, "complete and verify the selected root-cause method first")
    before = _audit_values(row)
    now = datetime.now(UTC)
    row.state = "action_planned"
    row.plan_summary = body.plan_summary
    row.planned_by_user_id = actor.user_id
    row.planned_at = now
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','plan',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.plan_started", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/implementation/start",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def start_implementation(
    request: Request,
    capa_id: UUID,
    body: CAPAStartImplementation,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version or row.state != "action_planned":
        raise HTTPException(409, "CAPA plan changed; refresh before implementation")
    if (
        db.scalar(
            select(QMSCAPAAction.id)
            .where(
                QMSCAPAAction.capa_id == row.id,
                QMSCAPAAction.tenant_id == actor.tenant_id,
                QMSCAPAAction.unit_id == row.unit_id,
                QMSCAPAAction.state == "open",
            )
            .limit(1)
        )
        is None
    ):
        raise HTTPException(422, "assign at least one action before implementation")
    before = _audit_values(row)
    now = datetime.now(UTC)
    row.state = "implementation"
    row.implementation_started_by_user_id = actor.user_id
    row.implementation_started_at = now
    row.row_version += 1
    row.updated_at = max(now, row.updated_at + timedelta(microseconds=1))
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','implement',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.implementation_started", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/effectiveness-review/start",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def start_effectiveness_review(
    request: Request,
    capa_id: UUID,
    body: CAPAStartEffectivenessReview,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", row.unit_id)
    if row.row_version != body.expected_version or row.state != "implementation":
        raise HTTPException(409, "CAPA implementation changed; refresh before review")
    states = list(
        db.scalars(
            select(QMSCAPAAction.state).where(
                QMSCAPAAction.capa_id == row.id,
                QMSCAPAAction.tenant_id == actor.tenant_id,
                QMSCAPAAction.unit_id == row.unit_id,
            )
        )
    )
    if not any(state in {"completed", "verified"} for state in states) or any(
        state in {"open", "in_progress"} for state in states
    ):
        raise HTTPException(422, "complete or verify all active actions before review")
    before = _audit_values(row)
    now = max(datetime.now(UTC), row.updated_at + timedelta(microseconds=1))
    row.state = "effectiveness_review"
    row.review_started_by_user_id = actor.user_id
    row.review_started_at = now
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','review',true)"))
        db.flush()
        _record(
            db, actor, request.state.request_id, row, "capa.effectiveness_review_started", before
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/{capa_id}/effectiveness-reviews", response_model=list[CAPAEffectivenessResponse])
def list_effectiveness_reviews(
    capa_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSCAPAEffectivenessReview]:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id)
    query = select(QMSCAPAEffectivenessReview).where(
        QMSCAPAEffectivenessReview.capa_id == parent.id,
        QMSCAPAEffectivenessReview.tenant_id == actor.tenant_id,
        QMSCAPAEffectivenessReview.unit_id == parent.unit_id,
    )
    return list(
        db.scalars(
            query.order_by(QMSCAPAEffectivenessReview.cycle_number.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/{capa_id}/effectiveness-reviews",
    response_model=CAPAEffectivenessResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def record_effectiveness_review(
    request: Request,
    capa_id: UUID,
    body: CAPAEffectivenessDecision,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPAEffectivenessReview:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.review", parent.unit_id)
    if parent.row_version != body.expected_version or parent.state != "effectiveness_review":
        raise HTTPException(409, "CAPA review changed; refresh before deciding")
    actions = list(
        db.scalars(
            select(QMSCAPAAction).where(
                QMSCAPAAction.capa_id == parent.id,
                QMSCAPAAction.tenant_id == actor.tenant_id,
                QMSCAPAAction.unit_id == parent.unit_id,
            )
        )
    )
    if any(action.completed_by_user_id == actor.user_id for action in actions):
        raise HTTPException(403, "action implementers cannot assess effectiveness")
    active_count = sum(action.state in {"completed", "verified"} for action in actions)
    verified_count = sum(action.state == "verified" for action in actions)
    cancelled_count = sum(action.state == "cancelled" for action in actions)
    if active_count < 1 or any(action.state in {"open", "in_progress"} for action in actions):
        raise HTTPException(409, "CAPA action status changed before assessment")
    cycle = (
        db.scalar(
            select(func.max(QMSCAPAEffectivenessReview.cycle_number)).where(
                QMSCAPAEffectivenessReview.capa_id == parent.id,
                QMSCAPAEffectivenessReview.tenant_id == actor.tenant_id,
                QMSCAPAEffectivenessReview.unit_id == parent.unit_id,
            )
        )
        or 0
    ) + 1
    now = datetime.now(UTC)
    if parent.review_started_at is None or parent.implementation_started_at is None:
        raise HTTPException(409, "CAPA review stamps are incomplete")
    review = QMSCAPAEffectivenessReview(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=parent.unit_id,
        capa_id=parent.id,
        cycle_number=cycle,
        decision=body.decision,
        notes=body.notes,
        reviewer_user_id=actor.user_id,
        reviewed_at=max(now, parent.review_started_at),
        implementation_started_by_user_id=parent.implementation_started_by_user_id,
        implementation_started_at=parent.implementation_started_at,
        review_started_by_user_id=parent.review_started_by_user_id,
        review_started_at=parent.review_started_at,
        active_action_count=active_count,
        verified_action_count=verified_count,
        cancelled_action_count=cancelled_count,
    )
    before = _audit_values(parent)
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','assess',true)"))
        db.add(review)
        db.flush()
        db.refresh(parent)
        _record_review(db, actor, request.state.request_id, review)
        _record(db, actor, request.state.request_id, parent, "capa.effectiveness_decided", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return review


@router.post(
    "/{capa_id}/close",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def close_capa(
    request: Request,
    capa_id: UUID,
    body: CAPAClose,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.review", row.unit_id)
    if row.row_version != body.expected_version or row.state != "effective":
        raise HTTPException(409, "CAPA effectiveness changed; refresh before closure")
    before = _audit_values(row)
    now = max(datetime.now(UTC), row.updated_at + timedelta(microseconds=1))
    row.state = "closed"
    row.closed_by_user_id = actor.user_id
    row.closed_at = now
    row.closure_notes = body.closure_notes
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','close',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.closed", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/cancel",
    response_model=CAPAResponse,
    dependencies=[Depends(require_csrf)],
)
def cancel_capa(
    request: Request,
    capa_id: UUID,
    body: CAPACancel,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPA:
    actor = actor_context(db, authenticated)
    row = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.review", row.unit_id)
    if row.row_version != body.expected_version or row.state in {"closed", "cancelled"}:
        raise HTTPException(409, "CAPA changed or is terminal; refresh before cancellation")
    before = _audit_values(row)
    now = max(datetime.now(UTC), row.updated_at + timedelta(microseconds=1))
    row.state = "cancelled"
    row.cancelled_by_user_id = actor.user_id
    row.cancelled_at = now
    row.cancellation_reason = body.reason
    row.row_version += 1
    row.updated_at = now
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','cancel',true)"))
        db.flush()
        _record(db, actor, request.state.request_id, row, "capa.cancelled", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/{capa_id}/actions", response_model=list[CAPAActionResponse])
def list_capa_actions(
    capa_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSCAPAAction]:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id)
    query = select(QMSCAPAAction).where(
        QMSCAPAAction.capa_id == parent.id,
        QMSCAPAAction.tenant_id == actor.tenant_id,
        QMSCAPAAction.unit_id == parent.unit_id,
    )
    return list(
        db.scalars(
            query.order_by(QMSCAPAAction.due_date, QMSCAPAAction.id).limit(limit).offset(offset)
        )
    )


@router.post(
    "/{capa_id}/actions",
    response_model=CAPAActionResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_capa_action(
    request: Request,
    capa_id: UUID,
    body: CAPAActionCreate,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPAAction:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", parent.unit_id)
    if parent.state != "action_planned" or parent.row_version != body.expected_capa_version:
        raise HTTPException(409, "CAPA plan changed; refresh before adding an action")
    now = datetime.now(UTC)
    row = QMSCAPAAction(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=parent.unit_id,
        capa_id=parent.id,
        title=body.title,
        description=body.description,
        owner_user_id=body.owner_user_id,
        due_date=body.due_date,
        state="open",
        completed_by_user_id=None,
        completed_at=None,
        verified_by_user_id=None,
        verified_at=None,
        verification_notes="",
        cancelled_by_user_id=None,
        cancelled_at=None,
        cancellation_reason="",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','action',true)"))
        db.add(row)
        db.flush()
        db.refresh(parent)
        _record_action(db, actor, request.state.request_id, row, "capa.action_created", None)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.patch(
    "/{capa_id}/actions/{action_id}",
    response_model=CAPAActionResponse,
    dependencies=[Depends(require_csrf)],
)
def update_capa_action(
    request: Request,
    capa_id: UUID,
    action_id: UUID,
    body: CAPAActionPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPAAction:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id, lock=True)
    require_capability(db, "capa.manage", parent.unit_id)
    row = db.scalar(
        select(QMSCAPAAction)
        .where(
            QMSCAPAAction.id == action_id,
            QMSCAPAAction.capa_id == parent.id,
            QMSCAPAAction.tenant_id == actor.tenant_id,
            QMSCAPAAction.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "CAPA action not found")
    if (
        parent.state != "action_planned"
        or parent.row_version != body.expected_capa_version
        or row.row_version != body.expected_action_version
    ):
        raise HTTPException(409, "CAPA action changed; refresh before editing")
    before = _action_values(row)
    for field, value in body.model_dump(
        exclude={"expected_capa_version", "expected_action_version"}, exclude_unset=True
    ).items():
        setattr(row, field, value)
    row.row_version += 1
    row.updated_at = max(datetime.now(UTC), row.updated_at + timedelta(microseconds=1))
    try:
        db.execute(text("SELECT set_config('app.capa_analysis_command','action',true)"))
        db.flush()
        db.refresh(parent)
        _record_action(db, actor, request.state.request_id, row, "capa.action_updated", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/{capa_id}/actions/{action_id}/transition",
    response_model=CAPAActionResponse,
    dependencies=[Depends(require_csrf)],
)
def transition_capa_action(
    request: Request,
    capa_id: UUID,
    action_id: UUID,
    body: CAPAActionTransition,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSCAPAAction:
    actor = actor_context(db, authenticated)
    parent = _row(db, actor, capa_id, lock=True)
    reviewer_step = body.target_state in {"verified", "cancelled"}
    require_capability(db, "capa.review" if reviewer_step else "capa.manage", parent.unit_id)
    row = db.scalar(
        select(QMSCAPAAction)
        .where(
            QMSCAPAAction.id == action_id,
            QMSCAPAAction.capa_id == parent.id,
            QMSCAPAAction.tenant_id == actor.tenant_id,
            QMSCAPAAction.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "CAPA action not found")
    if (
        parent.state != "implementation"
        or parent.row_version != body.expected_capa_version
        or row.row_version != body.expected_action_version
    ):
        raise HTTPException(409, "CAPA action changed; refresh before transition")
    allowed = {
        "open": {"in_progress", "completed", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": {"verified", "cancelled"},
    }
    if body.target_state not in allowed.get(row.state, set()):
        raise HTTPException(409, "invalid CAPA action transition")
    if body.target_state == "verified" and row.completed_by_user_id == actor.user_id:
        raise HTTPException(403, "the action implementer cannot verify their own work")
    before = _action_values(row)
    now = max(datetime.now(UTC), row.updated_at + timedelta(microseconds=1))
    row.state = body.target_state
    row.row_version += 1
    row.updated_at = now
    if body.target_state == "completed":
        row.completed_by_user_id = actor.user_id
        row.completed_at = now
    elif body.target_state == "verified":
        row.verified_by_user_id = actor.user_id
        row.verified_at = now
        row.verification_notes = body.verification_notes.strip()
    elif body.target_state == "cancelled":
        row.cancelled_by_user_id = actor.user_id
        row.cancelled_at = now
        row.cancellation_reason = body.cancellation_reason.strip()
    try:
        command = "verify" if reviewer_step else "progress"
        db.execute(
            text("SELECT set_config('app.capa_analysis_command',:command,true)"),
            {"command": command},
        )
        db.flush()
        db.refresh(parent)
        _record_action(db, actor, request.state.request_id, row, "capa.action_transitioned", before)
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row
