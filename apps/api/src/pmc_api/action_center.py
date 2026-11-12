"""Unified, tenant-scoped work queue derived from existing QMS records."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select, text
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated
from pmc_api.database import get_db
from pmc_api.models import (
    QMSCAPA,
    OrganizationUnit,
    QMSCAPAAction,
    QMSControlInstance,
    QMSControlInstanceActivity,
    QMSControlInstanceEvidence,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStepAssignment,
    WorkflowVersion,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context
from pmc_api.workflow_service import actor_is_eligible

router = APIRouter(prefix="/action-center", tags=["action-center"])
DBSession = Annotated[Session, Depends(get_db)]

Source = Literal["workflow", "capa", "control_activity", "evidence_review"]
Urgency = Literal["overdue", "due_soon", "normal", "waiting_review"]


class ActionItem(BaseModel):
    id: str
    source: Source
    source_id: UUID
    unit_id: UUID | None
    title: str
    context: str
    state: str
    urgency: Urgency
    due_date: date | None
    overdue: bool
    assigned_to_user_id: UUID | None
    assignee_name: str | None
    target_workspace: Literal["workflows", "capa", "controls"]
    target_record_id: UUID
    target_subrecord_id: UUID | None = None
    target_process_id: UUID | None = None
    updated_at: datetime


class ActionSummary(BaseModel):
    total: int
    overdue: int
    due_soon: int
    unassigned: int
    by_source: dict[str, int]


class ActionCenterResponse(BaseModel):
    scope: Literal["mine", "team"]
    generated_at: datetime
    summary: ActionSummary
    items: list[ActionItem]


def classify_urgency(
    due_date: date | None, *, today: date, waiting_review: bool = False
) -> Urgency:
    if waiting_review:
        return "waiting_review"
    if due_date is not None and due_date < today:
        return "overdue"
    if due_date is not None and due_date <= today + timedelta(days=7):
        return "due_soon"
    return "normal"


def summarize(items: list[ActionItem]) -> ActionSummary:
    sources = Counter(item.source for item in items)
    return ActionSummary(
        total=len(items),
        overdue=sum(item.overdue for item in items),
        due_soon=sum(item.urgency == "due_soon" for item in items),
        unassigned=sum(item.assigned_to_user_id is None for item in items),
        by_source=dict(sorted(sources.items())),
    )


def _can(db: Session, capability: str, unit_id: UUID) -> bool:
    return bool(
        db.scalar(
            text("SELECT qms_has_capability(:capability, :unit_id)"),
            {"capability": capability, "unit_id": unit_id},
        )
    )


def _can_review_evidence(db: Session, unit_id: UUID) -> bool:
    return all(
        _can(db, capability, unit_id)
        for capability in (
            "controls.read",
            "control_instances.read",
            "control_instances.manage",
            "evidence.review",
        )
    )


def _assignee_names(db: Session, items: list[ActionItem]) -> dict[UUID, str]:
    user_ids = {item.assigned_to_user_id for item in items if item.assigned_to_user_id}
    if not user_ids:
        return {}
    rows = db.execute(text("SELECT user_id, display_name FROM organization_member_directory()"))
    return {
        cast(UUID, user_id): cast(str, display_name)
        for user_id, display_name in rows
        if user_id in user_ids
    }


def _workflow_items(
    db: Session,
    actor: OrganizationActor,
    *,
    team: bool,
) -> list[ActionItem]:
    if not team and actor.role == "auditor":
        return []
    rows = list(
        db.execute(
            select(WorkflowInstance, WorkflowStep, WorkflowVersion, WorkflowDefinition)
            .join(
                WorkflowStep,
                and_(
                    WorkflowStep.id == WorkflowInstance.current_step_id,
                    WorkflowStep.tenant_id == WorkflowInstance.tenant_id,
                ),
            )
            .join(
                WorkflowVersion,
                and_(
                    WorkflowVersion.id == WorkflowInstance.workflow_version_id,
                    WorkflowVersion.tenant_id == WorkflowInstance.tenant_id,
                ),
            )
            .join(
                WorkflowDefinition,
                and_(
                    WorkflowDefinition.id == WorkflowVersion.definition_id,
                    WorkflowDefinition.tenant_id == WorkflowInstance.tenant_id,
                ),
            )
            .where(
                WorkflowInstance.tenant_id == actor.tenant_id,
                WorkflowInstance.status == "active",
                WorkflowStep.step_type.in_({"task", "approval"}),
            )
            .order_by(WorkflowInstance.updated_at.desc(), WorkflowInstance.id)
            .limit(250)
        )
    )
    items: list[ActionItem] = []
    for instance, step, _version, definition in rows:
        if not team and not actor_is_eligible(db, actor, step.id, instance.workflow_version_id):
            continue
        assignments = list(
            db.scalars(
                select(WorkflowStepAssignment).where(
                    WorkflowStepAssignment.tenant_id == actor.tenant_id,
                    WorkflowStepAssignment.workflow_version_id == instance.workflow_version_id,
                    WorkflowStepAssignment.step_id == step.id,
                )
            )
        )
        direct_user = next(
            (
                assignment.target_user_id
                for assignment in assignments
                if assignment.target_type == "user"
            ),
            None,
        )
        items.append(
            ActionItem(
                id=f"workflow:{instance.id}",
                source="workflow",
                source_id=instance.id,
                unit_id=None,
                title=instance.title,
                context=f"{definition.name} · {step.name}",
                state="approval" if step.step_type == "approval" else "task",
                urgency="normal",
                due_date=None,
                overdue=False,
                assigned_to_user_id=direct_user,
                assignee_name=None,
                target_workspace="workflows",
                target_record_id=instance.id,
                updated_at=instance.updated_at,
            )
        )
    return items


def _capa_items(
    db: Session,
    actor: OrganizationActor,
    *,
    team: bool,
    unit_id: UUID | None,
    today: date,
) -> list[ActionItem]:
    query = (
        select(QMSCAPAAction, QMSCAPA)
        .join(
            QMSCAPA,
            and_(
                QMSCAPA.id == QMSCAPAAction.capa_id,
                QMSCAPA.tenant_id == QMSCAPAAction.tenant_id,
                QMSCAPA.unit_id == QMSCAPAAction.unit_id,
            ),
        )
        .where(
            QMSCAPAAction.tenant_id == actor.tenant_id,
            QMSCAPAAction.state.in_({"open", "completed"}),
        )
    )
    if unit_id is not None:
        query = query.where(QMSCAPAAction.unit_id == unit_id)
    rows = list(db.execute(query.order_by(QMSCAPAAction.due_date, QMSCAPAAction.id).limit(250)))
    permission_cache: dict[UUID, bool] = {}
    items: list[ActionItem] = []
    for action, capa in rows:
        waiting_review = action.state == "completed"
        if not team:
            if not waiting_review and action.owner_user_id != actor.user_id:
                continue
            if waiting_review:
                if action.unit_id not in permission_cache:
                    permission_cache[action.unit_id] = _can(db, "capa.review", action.unit_id)
                if (
                    not permission_cache[action.unit_id]
                    or action.completed_by_user_id == actor.user_id
                ):
                    continue
        urgency = classify_urgency(action.due_date, today=today, waiting_review=waiting_review)
        items.append(
            ActionItem(
                id=f"capa:{action.id}",
                source="capa",
                source_id=action.id,
                unit_id=action.unit_id,
                title=action.title,
                context=f"{capa.code} · {capa.name}",
                state="awaiting_verification" if waiting_review else "open",
                urgency=urgency,
                due_date=action.due_date,
                overdue=urgency == "overdue",
                assigned_to_user_id=(None if waiting_review else action.owner_user_id),
                assignee_name=None,
                target_workspace="capa",
                target_record_id=capa.id,
                target_subrecord_id=action.id,
                target_process_id=capa.process_id,
                updated_at=action.updated_at,
            )
        )
    return items


def _control_items(
    db: Session,
    actor: OrganizationActor,
    *,
    team: bool,
    unit_id: UUID | None,
    today: date,
) -> list[ActionItem]:
    activity_query = (
        select(QMSControlInstanceActivity, QMSControlInstance)
        .join(
            QMSControlInstance,
            and_(
                QMSControlInstance.id == QMSControlInstanceActivity.control_instance_id,
                QMSControlInstance.tenant_id == QMSControlInstanceActivity.tenant_id,
                QMSControlInstance.unit_id == QMSControlInstanceActivity.unit_id,
            ),
        )
        .where(
            QMSControlInstanceActivity.tenant_id == actor.tenant_id,
            QMSControlInstanceActivity.status != "completed",
            QMSControlInstance.status == "active",
        )
    )
    if unit_id is not None:
        activity_query = activity_query.where(QMSControlInstanceActivity.unit_id == unit_id)
    activity_rows = list(
        db.execute(
            activity_query.order_by(
                QMSControlInstanceActivity.target_date,
                QMSControlInstanceActivity.sequence,
                QMSControlInstanceActivity.id,
            ).limit(250)
        )
    )
    items: list[ActionItem] = []
    for activity, instance in activity_rows:
        if not team and activity.assigned_to_user_id != actor.user_id:
            continue
        urgency = classify_urgency(activity.target_date, today=today)
        items.append(
            ActionItem(
                id=f"control_activity:{activity.id}",
                source="control_activity",
                source_id=activity.id,
                unit_id=activity.unit_id,
                title=activity.name,
                context=f"{instance.code} · {instance.name}",
                state=activity.status,
                urgency=urgency,
                due_date=activity.target_date,
                overdue=urgency == "overdue",
                assigned_to_user_id=activity.assigned_to_user_id,
                assignee_name=None,
                target_workspace="controls",
                target_record_id=instance.id,
                target_subrecord_id=activity.id,
                target_process_id=instance.process_id,
                updated_at=activity.updated_at,
            )
        )

    evidence_query = (
        select(QMSControlInstanceEvidence, QMSControlInstance)
        .join(
            QMSControlInstance,
            and_(
                QMSControlInstance.id == QMSControlInstanceEvidence.control_instance_id,
                QMSControlInstance.tenant_id == QMSControlInstanceEvidence.tenant_id,
                QMSControlInstance.unit_id == QMSControlInstanceEvidence.unit_id,
            ),
        )
        .where(
            QMSControlInstanceEvidence.tenant_id == actor.tenant_id,
            QMSControlInstanceEvidence.status == "submitted",
            QMSControlInstance.status == "active",
        )
    )
    if unit_id is not None:
        evidence_query = evidence_query.where(QMSControlInstanceEvidence.unit_id == unit_id)
    review_cache: dict[UUID, bool] = {}
    for evidence, instance in db.execute(
        evidence_query.order_by(
            QMSControlInstanceEvidence.updated_at, QMSControlInstanceEvidence.id
        ).limit(250)
    ):
        if not team:
            if evidence.unit_id not in review_cache:
                review_cache[evidence.unit_id] = _can_review_evidence(db, evidence.unit_id)
            if not review_cache[evidence.unit_id] or evidence.submitted_by_user_id == actor.user_id:
                continue
        items.append(
            ActionItem(
                id=f"evidence_review:{evidence.id}",
                source="evidence_review",
                source_id=evidence.id,
                unit_id=evidence.unit_id,
                title=f"Review evidence: {evidence.name}",
                context=f"{instance.code} · {instance.name}",
                state="submitted",
                urgency="waiting_review",
                due_date=None,
                overdue=False,
                assigned_to_user_id=None,
                assignee_name=None,
                target_workspace="controls",
                target_record_id=instance.id,
                target_subrecord_id=evidence.id,
                target_process_id=instance.process_id,
                updated_at=evidence.updated_at,
            )
        )
    return items


def _sort_key(item: ActionItem) -> tuple[int, date, float, str]:
    rank = {"overdue": 0, "waiting_review": 1, "due_soon": 2, "normal": 3}[item.urgency]
    return (rank, item.due_date or date.max, -item.updated_at.timestamp(), item.id)


@router.get("", response_model=ActionCenterResponse)
def action_center(
    db: DBSession,
    authenticated: Authenticated,
    scope: Literal["mine", "team"] = "mine",
    unit_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ActionCenterResponse:
    actor = actor_context(db, authenticated)
    team = scope == "team"
    if team and actor.role not in {"owner", "admin", "auditor"}:
        raise HTTPException(403, "team action center requires an authorized oversight role")
    if unit_id is not None:
        active_unit = db.scalar(
            select(OrganizationUnit.id).where(
                OrganizationUnit.id == unit_id,
                OrganizationUnit.tenant_id == actor.tenant_id,
                OrganizationUnit.status == "active",
            )
        )
        if active_unit is None:
            raise HTTPException(404, "organization unit not found")

    now = datetime.now(UTC)
    items = [
        *_workflow_items(db, actor, team=team),
        *_capa_items(db, actor, team=team, unit_id=unit_id, today=now.date()),
        *_control_items(db, actor, team=team, unit_id=unit_id, today=now.date()),
    ]
    names = _assignee_names(db, items)
    enriched = [
        item.model_copy(
            update={
                "assignee_name": (
                    names.get(item.assigned_to_user_id) if item.assigned_to_user_id else None
                )
            }
        )
        for item in items
    ]
    ordered = sorted(enriched, key=_sort_key)[:limit]
    return ActionCenterResponse(
        scope=scope,
        generated_at=now,
        summary=summarize(enriched),
        items=ordered,
    )
