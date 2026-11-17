"""Unified, tenant-scoped work queue derived from existing QMS records."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pmc_api.action_center_queries import queue_statement, workflow_query
from pmc_api.auth import Authenticated
from pmc_api.database import get_db
from pmc_api.models import OrganizationUnit, WorkflowInstance
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context

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
    # Retained for the existing workflow integration boundary. Production uses
    # the unified statement below, including its complete summary.
    query = workflow_query(actor, team=team, today=datetime.now(UTC).date())
    rows = db.execute(
        query.order_by(WorkflowInstance.updated_at.desc(), WorkflowInstance.id).limit(200)
    ).mappings()
    return [ActionItem.model_validate({**row, "assignee_name": None}) for row in rows]


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
    result = list(
        db.execute(
            queue_statement(
                actor,
                team=team,
                today=now.date(),
                unit_id=unit_id,
                limit=limit,
            )
        ).mappings()
    )
    totals = result[0]
    items = [
        ActionItem.model_validate({**row, "assignee_name": None})
        for row in result
        if row["id"] is not None
    ]
    names = _assignee_names(db, items)
    current_actor = actor_context(db, authenticated)
    if current_actor.role != actor.role:
        raise HTTPException(409, "action center context changed; refresh before continuing")
    return ActionCenterResponse(
        scope=scope,
        generated_at=now,
        summary=ActionSummary(
            total=totals["total"],
            overdue=totals["overdue_count"],
            due_soon=totals["due_soon_count"],
            unassigned=totals["unassigned_count"],
            by_source=totals["by_source"],
        ),
        items=[
            item.model_copy(
                update={
                    "assignee_name": names.get(item.assigned_to_user_id)
                    if item.assigned_to_user_id
                    else None
                }
            )
            for item in items
        ],
    )
