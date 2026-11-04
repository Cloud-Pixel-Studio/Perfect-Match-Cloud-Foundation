"""Controlled work items generated from active control method definitions."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import QMSControlInstance, QMSControlInstanceActivity
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(tags=["control-instance-activities"])
DBSession = Annotated[Session, Depends(get_db)]
TextField = Annotated[str, StringConstraints(max_length=4000)]
STATES = "not_started in_progress blocked under_review completed"


class ActivityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    assigned_to_user_id: UUID | None = None
    target_date: date | None = None
    notes: TextField | None = None


class ActivityTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    target_status: Annotated[str, StringConstraints(pattern=f"^({'|'.join(STATES.split())})$")]
    decision: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    completion_summary: TextField = ""


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    control_instance_id: UUID
    activity_definition_id: UUID
    sequence: int
    name: str
    description: str
    objective: str
    why_it_matters: str
    implementation_steps: str
    success_criteria: str
    activity_kind: str
    readiness_required: bool
    responsible_role: str
    expected_output: str
    evidence_expectations: str
    assigned_to_user_id: UUID | None
    status: str
    target_date: date | None
    completion_summary: str
    notes: str
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    row_version: int
    created_at: datetime
    updated_at: datetime


def _audit_values(row: QMSControlInstanceActivity) -> dict[str, object]:
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    return {
        "unit_id": str(row.unit_id),
        "process_id": str(row.process_id),
        "control_id": str(row.control_id),
        "control_instance_id": str(row.control_instance_id),
        "activity_definition_id": str(row.activity_definition_id),
        "sequence": row.sequence,
        "name": row.name,
        "description_hash": digest(row.description),
        "objective_hash": digest(row.objective),
        "why_it_matters_hash": digest(row.why_it_matters),
        "implementation_steps_hash": digest(row.implementation_steps),
        "success_criteria_hash": digest(row.success_criteria),
        "activity_kind": row.activity_kind,
        "readiness_required": row.readiness_required,
        "responsible_role": row.responsible_role,
        "expected_output_hash": digest(row.expected_output),
        "evidence_expectations_hash": digest(row.evidence_expectations),
        "assigned_to_user_id": str(row.assigned_to_user_id) if row.assigned_to_user_id else None,
        "status": row.status,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "completion_summary_hash": digest(row.completion_summary),
        "notes_hash": digest(row.notes),
        "completed_by_user_id": str(row.completed_by_user_id) if row.completed_by_user_id else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "row_version": row.row_version,
    }


def _record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSControlInstanceActivity,
    action: str,
    old: dict[str, object] | None,
    decision: str | None = None,
) -> None:
    new = _audit_values(row)
    if decision is not None:
        new["decision"] = decision
    audit_service.record_control(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=row.id,
        request_id=request_id,
        old_values=old,
        new_values=new,
    )


def _db_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(409, "activity, assignee, state or version conflicts") from None
    if state == "42501":
        raise HTTPException(403, "control authority denied") from None
    raise error


@router.get("/control-instance-activities", response_model=list[ActivityResponse])
def list_activities(
    db: DBSession,
    authenticated: Authenticated,
    instance_id: UUID,
    limit: int = Query(100, ge=1, le=200),
) -> list[QMSControlInstanceActivity]:
    actor = actor_context(db, authenticated)
    parent = db.scalar(
        select(QMSControlInstance).where(
            QMSControlInstance.id == instance_id,
            QMSControlInstance.tenant_id == actor.tenant_id,
            QMSControlInstance.status == "active",
        )
    )
    if parent is None:
        raise HTTPException(404, "control implementation not found")
    require_capability(db, "control_instances.read", parent.unit_id)
    return list(
        db.scalars(
            select(QMSControlInstanceActivity)
            .where(
                QMSControlInstanceActivity.control_instance_id == parent.id,
                QMSControlInstanceActivity.tenant_id == actor.tenant_id,
            )
            .order_by(QMSControlInstanceActivity.sequence, QMSControlInstanceActivity.id)
            .limit(limit)
        )
    )


@router.patch(
    "/control-instance-activities/{activity_id}",
    response_model=ActivityResponse,
    dependencies=[Depends(require_csrf)],
)
def update_activity(
    request: Request,
    activity_id: UUID,
    body: ActivityPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstanceActivity:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSControlInstanceActivity)
        .where(
            QMSControlInstanceActivity.id == activity_id,
            QMSControlInstanceActivity.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "implementation activity not found")
    require_capability(db, "control_instances.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "activity changed; refresh before editing")
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes:
        raise HTTPException(422, "provide activity changes")
    before = _audit_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _record(
            db,
            actor,
            request.state.request_id,
            row,
            "control_instance_activity.updated",
            before,
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/control-instance-activities/{activity_id}/transition",
    response_model=ActivityResponse,
    dependencies=[Depends(require_csrf)],
)
def transition_activity(
    request: Request,
    activity_id: UUID,
    body: ActivityTransition,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstanceActivity:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSControlInstanceActivity).where(
            QMSControlInstanceActivity.id == activity_id,
            QMSControlInstanceActivity.tenant_id == actor.tenant_id,
        )
    )
    if row is None:
        raise HTTPException(404, "implementation activity not found")
    # Lock the parent first, matching implementation transitions and avoiding lock-order inversions.
    parent = db.scalar(
        select(QMSControlInstance)
        .where(
            QMSControlInstance.id == row.control_instance_id,
            QMSControlInstance.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    if parent is None or parent.status != "active":
        raise HTTPException(409, "implementation is not active")
    require_capability(db, "control_instances.manage", row.unit_id)
    row = db.scalar(
        select(QMSControlInstanceActivity)
        .where(
            QMSControlInstanceActivity.id == activity_id,
            QMSControlInstanceActivity.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "implementation activity not found")
    if row.row_version != body.expected_version:
        raise HTTPException(409, "activity changed; refresh before editing")
    allowed = {
        "not_started": {"in_progress"},
        "in_progress": {"blocked", "under_review"},
        "blocked": {"in_progress", "under_review"},
        "under_review": {"in_progress", "completed"},
        "completed": set(),
    }
    if body.target_status not in allowed[row.status]:
        raise HTTPException(409, "invalid implementation activity transition")
    if body.target_status == "completed" and not body.completion_summary.strip():
        raise HTTPException(422, "completion requires a summary")
    before = _audit_values(row)
    row.status = body.target_status
    if body.target_status == "completed":
        row.completion_summary = body.completion_summary
        row.completed_by_user_id = actor.user_id
        row.completed_at = datetime.now(UTC)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.connection().exec_driver_sql(
            "SELECT set_config('app.control_activity_workflow','on',true)"
        )
        db.flush()
        _record(
            db,
            actor,
            request.state.request_id,
            row,
            "control_instance_activity.transitioned",
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
