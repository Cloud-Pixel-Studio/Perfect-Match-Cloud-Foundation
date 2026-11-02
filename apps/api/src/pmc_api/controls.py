"""Tenant- and unit-scoped controls and controlled implementation transitions."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.control_instance_activities import _audit_values as _instance_activity_values
from pmc_api.control_instance_evidence import generate_for_instance as _generate_instance_evidence
from pmc_api.database import get_db
from pmc_api.models import (
    QMSControl,
    QMSControlActivity,
    QMSControlInstance,
    QMSControlInstanceActivity,
    QMSControlInstanceEvidence,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(tags=["controls"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
TextField = Annotated[str, StringConstraints(max_length=4000)]
CATEGORIES = (
    "governance process document_control evidence supplier training performance improvement other"
)
STATUSES = "not_started in_progress evidence_required under_review implemented not_applicable"


class ControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    process_id: UUID
    code: Code
    name: Name
    objective: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    description: TextField = ""
    category: Annotated[str, StringConstraints(pattern=f"^({'|'.join(CATEGORIES.split())})$")] = (
        "process"
    )
    guidance_purpose: TextField = ""
    guidance_why: TextField = ""
    implementation_guidance: TextField = ""
    recommended_steps: TextField = ""
    recommended_tools: TextField = ""
    evidence_guidance: TextField = ""
    practical_notes: TextField = ""
    owner_user_id: UUID | None = None


class ControlPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    code: Code | None = None
    name: Name | None = None
    objective: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
        | None
    ) = None
    description: TextField | None = None
    category: (
        Annotated[str, StringConstraints(pattern=f"^({'|'.join(CATEGORIES.split())})$")] | None
    ) = None
    guidance_purpose: TextField | None = None
    guidance_why: TextField | None = None
    implementation_guidance: TextField | None = None
    recommended_steps: TextField | None = None
    recommended_tools: TextField | None = None
    evidence_guidance: TextField | None = None
    practical_notes: TextField | None = None
    owner_user_id: UUID | None = None


class ControlResponse(ControlInput):
    id: UUID
    state: str
    row_version: int
    created_at: datetime
    updated_at: datetime


class InstanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control_id: UUID
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    name: Name
    owner_user_id: UUID | None = None
    applicability: Annotated[
        str, StringConstraints(pattern="^(applicable|conditional|not_applicable)$")
    ] = "applicable"
    justification: TextField = ""
    target_date: date | None = None
    review_date: date | None = None
    notes: TextField = ""

    @model_validator(mode="after")
    def validate_not_applicable(self) -> InstanceInput:
        if self.applicability == "not_applicable" and not self.justification.strip():
            raise ValueError("not-applicable decisions require a justification")
        return self


class InstancePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
    ) = None
    name: Name | None = None
    owner_user_id: UUID | None = None
    applicability: (
        Annotated[str, StringConstraints(pattern="^(applicable|conditional|not_applicable)$")]
        | None
    ) = None
    justification: TextField | None = None
    target_date: date | None = None
    review_date: date | None = None
    notes: TextField | None = None


class TransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_status: Annotated[str, StringConstraints(pattern=f"^({'|'.join(STATUSES.split())})$")]
    decision: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ControlVersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class InstanceResponse(InstanceInput):
    id: UUID
    unit_id: UUID
    process_id: UUID
    implementation_status: str
    implementation_date: date | None
    status: str
    row_version: int
    created_at: datetime
    updated_at: datetime


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _control_values(row: QMSControl) -> dict[str, object]:
    return {
        "unit_id": str(row.unit_id),
        "process_id": str(row.process_id),
        "code": row.code,
        "name": row.name,
        "objective_hash": _hash(row.objective),
        "description_hash": _hash(row.description),
        "category": row.category,
        "guidance_hashes": {
            key: _hash(getattr(row, key))
            for key in (
                "guidance_purpose",
                "guidance_why",
                "implementation_guidance",
                "recommended_steps",
                "recommended_tools",
                "evidence_guidance",
                "practical_notes",
            )
        },
        "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
        "state": row.state,
        "row_version": row.row_version,
    }


def _instance_values(row: QMSControlInstance) -> dict[str, object]:
    return {
        "unit_id": str(row.unit_id),
        "process_id": str(row.process_id),
        "control_id": str(row.control_id),
        "code": row.code,
        "name": row.name,
        "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
        "implementation_status": row.implementation_status,
        "applicability": row.applicability,
        "justification_hash": _hash(row.justification),
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "implementation_date": row.implementation_date.isoformat()
        if row.implementation_date
        else None,
        "review_date": row.review_date.isoformat() if row.review_date else None,
        "notes_hash": _hash(row.notes),
        "status": row.status,
        "row_version": row.row_version,
    }


def _database_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(409, "control, process, owner, state or version conflicts") from None
    if state == "42501":
        raise HTTPException(403, "control authority denied") from None
    raise error


def _audit(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSControl | QMSControlInstance,
    action: str,
    before: dict[str, object] | None,
    decision: str | None = None,
) -> None:
    after = _control_values(row) if isinstance(row, QMSControl) else _instance_values(row)
    if decision is not None:
        after["decision"] = decision
    audit_service.record_control(
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


def create_control(
    db: Session, actor: OrganizationActor, request_id: UUID, body: ControlInput
) -> QMSControl:
    require_capability(db, "controls.manage", body.unit_id)
    require_capability(db, "processes.read", body.unit_id)
    now = datetime.now(UTC)
    row = QMSControl(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        state="draft",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        _audit(db, actor, request_id, row, "control.created", None)
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def update_control(
    db: Session, actor: OrganizationActor, request_id: UUID, control_id: UUID, body: ControlPatch
) -> QMSControl:
    row = db.scalar(
        select(QMSControl)
        .where(QMSControl.id == control_id, QMSControl.tenant_id == actor.tenant_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "control not found")
    require_capability(db, "controls.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "control changed; refresh before editing")
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes or any(
        value is None and key != "owner_user_id" for key, value in changes.items()
    ):
        raise HTTPException(422, "provide non-null control changes")
    before = _control_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _audit(db, actor, request_id, row, "control.updated", before)
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def change_control_state(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    control_id: UUID,
    expected_version: int,
    state: str,
) -> QMSControl:
    row = db.scalar(
        select(QMSControl)
        .where(QMSControl.id == control_id, QMSControl.tenant_id == actor.tenant_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "control not found")
    require_capability(db, "controls.manage", row.unit_id)
    require_capability(db, "processes.read", row.unit_id)
    if row.row_version != expected_version:
        raise HTTPException(409, "control changed; refresh before editing")
    if row.state == state:
        raise HTTPException(409, "control is already in that state")
    before = _control_values(row)
    row.state = state
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            row,
            "control.activated" if state == "active" else "control.retired",
            before,
        )
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def create_instance(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    unit_id: UUID,
    process_id: UUID,
    body: InstanceInput,
) -> QMSControlInstance:
    require_capability(db, "control_instances.manage", unit_id)
    require_capability(db, "controls.read", unit_id)
    now = datetime.now(UTC)
    row = QMSControlInstance(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=unit_id,
        process_id=process_id,
        **body.model_dump(),
        implementation_status="not_applicable"
        if body.applicability == "not_applicable"
        else "not_started",
        implementation_date=None,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        if body.applicability != "not_applicable":
            definitions = db.scalars(
                select(QMSControlActivity)
                .where(
                    QMSControlActivity.tenant_id == actor.tenant_id,
                    QMSControlActivity.unit_id == unit_id,
                    QMSControlActivity.process_id == process_id,
                    QMSControlActivity.control_id == body.control_id,
                    QMSControlActivity.active.is_(True),
                )
                .order_by(QMSControlActivity.sequence, QMSControlActivity.id)
            ).all()
            for definition in definitions:
                task = QMSControlInstanceActivity(
                    id=uuid4(),
                    tenant_id=actor.tenant_id,
                    unit_id=unit_id,
                    process_id=process_id,
                    control_id=body.control_id,
                    control_instance_id=row.id,
                    activity_definition_id=definition.id,
                    sequence=definition.sequence,
                    name=definition.name,
                    description=definition.description,
                    objective=definition.objective,
                    why_it_matters=definition.why_it_matters,
                    implementation_steps=definition.implementation_steps,
                    success_criteria=definition.success_criteria,
                    activity_kind=definition.activity_kind,
                    readiness_required=definition.readiness_required,
                    responsible_role=definition.responsible_role,
                    expected_output=definition.expected_output,
                    evidence_expectations=definition.evidence_expectations,
                    assigned_to_user_id=None,
                    status="not_started",
                    target_date=None,
                    completion_summary="",
                    notes="",
                    completed_by_user_id=None,
                    completed_at=None,
                    row_version=1,
                    created_by_user_id=actor.user_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(task)
                db.flush()
                audit_service.record_control(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.user_id,
                    actor_display_name=actor.display_name,
                    actor_role=actor.role,
                    action="control_instance_activity.created",
                    resource_id=task.id,
                    request_id=request_id,
                    old_values=None,
                    new_values=_instance_activity_values(task),
                )
            _generate_instance_evidence(db, actor, request_id, row, now)
        _audit(db, actor, request_id, row, "control_instance.created", None)
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def update_instance(
    db: Session, actor: OrganizationActor, request_id: UUID, instance_id: UUID, body: InstancePatch
) -> QMSControlInstance:
    row = db.scalar(
        select(QMSControlInstance)
        .where(
            QMSControlInstance.id == instance_id, QMSControlInstance.tenant_id == actor.tenant_id
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "control implementation not found")
    require_capability(db, "control_instances.manage", row.unit_id)
    require_capability(db, "controls.read", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "implementation changed; refresh before editing")
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes or any(
        value is None and key not in {"owner_user_id", "target_date", "review_date"}
        for key, value in changes.items()
    ):
        raise HTTPException(422, "provide non-null implementation changes")
    if (
        changes.get("applicability") == "not_applicable"
        and not (changes.get("justification") or row.justification).strip()
    ):
        raise HTTPException(422, "not-applicable decisions require a justification")
    before = _instance_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    if row.applicability == "not_applicable":
        row.implementation_status = "not_applicable"
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _audit(db, actor, request_id, row, "control_instance.updated", before)
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def transition_instance(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    instance_id: UUID,
    body: TransitionInput,
) -> QMSControlInstance:
    row = db.scalar(
        select(QMSControlInstance)
        .where(
            QMSControlInstance.id == instance_id, QMSControlInstance.tenant_id == actor.tenant_id
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "control implementation not found")
    require_capability(db, "control_instances.manage", row.unit_id)
    require_capability(db, "controls.read", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "implementation changed; refresh before editing")
    if body.target_status in {"under_review", "implemented"}:
        incomplete_required = db.scalar(
            select(func.count())
            .select_from(QMSControlInstanceActivity)
            .where(
                QMSControlInstanceActivity.tenant_id == actor.tenant_id,
                QMSControlInstanceActivity.control_instance_id == row.id,
                QMSControlInstanceActivity.readiness_required.is_(True),
                QMSControlInstanceActivity.status != "completed",
            )
        )
        incomplete_evidence = db.scalar(
            select(func.count())
            .select_from(QMSControlInstanceEvidence)
            .where(
                QMSControlInstanceEvidence.tenant_id == actor.tenant_id,
                QMSControlInstanceEvidence.control_instance_id == row.id,
                QMSControlInstanceEvidence.mandatory.is_(True),
                QMSControlInstanceEvidence.status != "accepted",
            )
        )
        if incomplete_required or incomplete_evidence:
            raise HTTPException(
                409, "required implementation activities and evidence must be complete first"
            )
    before = _instance_values(row)
    row.implementation_status = body.target_status
    row.applicability = (
        "not_applicable" if body.target_status == "not_applicable" else row.applicability
    )
    if body.target_status == "not_applicable":
        row.justification = body.decision
    row.implementation_date = (
        datetime.now(UTC).date() if body.target_status == "implemented" else row.implementation_date
    )
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _audit(db, actor, request_id, row, "control_instance.transitioned", before, body.decision)
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/controls", response_model=list[ControlResponse])
def list_controls(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    process_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> list[QMSControl]:
    actor = actor_context(db, authenticated)
    require_capability(db, "controls.read", unit_id)
    query = select(QMSControl).where(
        QMSControl.tenant_id == actor.tenant_id, QMSControl.unit_id == unit_id
    )
    if process_id:
        query = query.where(QMSControl.process_id == process_id)
    return list(db.scalars(query.order_by(QMSControl.code, QMSControl.id).limit(limit)))


@router.post(
    "/controls",
    response_model=ControlResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_control_route(
    request: Request, body: ControlInput, db: DBSession, authenticated: Authenticated
) -> QMSControl:
    return create_control(db, actor_context(db, authenticated), request.state.request_id, body)


@router.patch(
    "/controls/{control_id}", response_model=ControlResponse, dependencies=[Depends(require_csrf)]
)
def update_control_route(
    request: Request,
    control_id: UUID,
    body: ControlPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControl:
    return update_control(
        db, actor_context(db, authenticated), request.state.request_id, control_id, body
    )


def _change_control_state_route(
    request: Request,
    control_id: UUID,
    body: ControlVersionInput,
    db: DBSession,
    authenticated: Authenticated,
    target_state: str,
) -> QMSControl:
    return change_control_state(
        db,
        actor_context(db, authenticated),
        request.state.request_id,
        control_id,
        body.expected_version,
        target_state,
    )


@router.post(
    "/controls/{control_id}/activate",
    response_model=ControlResponse,
    dependencies=[Depends(require_csrf)],
)
def activate_control_route(
    request: Request,
    control_id: UUID,
    body: ControlVersionInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControl:
    return _change_control_state_route(request, control_id, body, db, authenticated, "active")


@router.post(
    "/controls/{control_id}/retire",
    response_model=ControlResponse,
    dependencies=[Depends(require_csrf)],
)
def retire_control_route(
    request: Request,
    control_id: UUID,
    body: ControlVersionInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControl:
    return _change_control_state_route(request, control_id, body, db, authenticated, "retired")


@router.get("/control-instances", response_model=list[InstanceResponse])
def list_instances(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    process_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None, max_length=160),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[QMSControlInstance]:
    actor = actor_context(db, authenticated)
    require_capability(db, "control_instances.read", unit_id)
    query = select(QMSControlInstance).where(
        QMSControlInstance.tenant_id == actor.tenant_id,
        QMSControlInstance.unit_id == unit_id,
        QMSControlInstance.status == "active",
    )
    if process_id:
        query = query.where(QMSControlInstance.process_id == process_id)
    if search and search.strip():
        literal = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                QMSControlInstance.code.ilike(f"%{literal}%", escape="\\"),
                QMSControlInstance.name.ilike(f"%{literal}%", escape="\\"),
            )
        )
    return list(
        db.scalars(
            query.order_by(QMSControlInstance.code, QMSControlInstance.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/control-instances",
    response_model=InstanceResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_instance_route(
    request: Request,
    unit_id: UUID,
    process_id: UUID,
    body: InstanceInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstance:
    return create_instance(
        db, actor_context(db, authenticated), request.state.request_id, unit_id, process_id, body
    )


@router.patch(
    "/control-instances/{instance_id}",
    response_model=InstanceResponse,
    dependencies=[Depends(require_csrf)],
)
def update_instance_route(
    request: Request,
    instance_id: UUID,
    body: InstancePatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstance:
    return update_instance(
        db, actor_context(db, authenticated), request.state.request_id, instance_id, body
    )


@router.post(
    "/control-instances/{instance_id}/transition",
    response_model=InstanceResponse,
    dependencies=[Depends(require_csrf)],
)
def transition_instance_route(
    request: Request,
    instance_id: UUID,
    body: TransitionInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstance:
    return transition_instance(
        db, actor_context(db, authenticated), request.state.request_id, instance_id, body
    )
