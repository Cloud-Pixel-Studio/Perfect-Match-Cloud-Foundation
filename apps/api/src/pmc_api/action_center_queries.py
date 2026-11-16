"""Read-only queue projections. Eligibility precedes pagination under existing RLS."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Date,
    Select,
    String,
    Uuid,
    and_,
    case,
    cast,
    false,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import ColumnElement

from pmc_api.models import (
    QMSCAPA,
    OrganizationUnit,
    OrganizationUnitAssignment,
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


def capability(name: str, unit: Any) -> ColumnElement[bool]:
    return func.public.qms_has_capability(name, unit).is_(True)


def projection(
    source: str,
    *,
    identifier: Any,
    unit: Any,
    title: Any,
    context: Any,
    state: Any,
    due: Any,
    assigned: Any,
    workspace: str,
    parent: Any,
    child: Any,
    process: Any,
    updated: Any,
    today: date,
    waiting: Any = False,
) -> Select[Any]:
    urgency = case(
        (waiting, "waiting_review"),
        (due < today, "overdue"),
        (due <= today + timedelta(days=7), "due_soon"),
        else_="normal",
    )
    return select(
        (literal(source + ":") + cast(identifier, String)).label("id"),
        literal(source).label("source"),
        identifier.label("source_id"),
        unit.label("unit_id"),
        title.label("title"),
        context.label("context"),
        state.label("state"),
        urgency.label("urgency"),
        due.label("due_date"),
        (urgency == "overdue").label("overdue"),
        assigned.label("assigned_to_user_id"),
        literal(workspace).label("target_workspace"),
        parent.label("target_record_id"),
        child.label("target_subrecord_id"),
        process.label("target_process_id"),
        updated.label("updated_at"),
    )


def workflow_query(actor: OrganizationActor, *, team: bool, today: date) -> Select[Any]:
    instance, step, version, definition = (
        WorkflowInstance,
        WorkflowStep,
        WorkflowVersion,
        WorkflowDefinition,
    )
    assignment = WorkflowStepAssignment
    assigned = (
        select(assignment.target_user_id)
        .where(
            assignment.tenant_id == actor.tenant_id,
            assignment.workflow_version_id == instance.workflow_version_id,
            assignment.step_id == instance.current_step_id,
            assignment.target_type == "user",
        )
        .order_by(assignment.target_user_id)
        .limit(1)
        .correlate(instance)
        .scalar_subquery()
    )
    query = (
        projection(
            "workflow",
            identifier=instance.id,
            unit=cast(literal(None), Uuid),
            title=instance.title,
            context=definition.name + " · " + step.name,
            state=case((step.step_type == "approval", "approval"), else_="task"),
            due=cast(literal(None), Date),
            assigned=assigned,
            workspace="workflows",
            parent=instance.id,
            child=cast(literal(None), Uuid),
            process=cast(literal(None), Uuid),
            updated=instance.updated_at,
            today=today,
        )
        .select_from(instance)
        .join(
            step,
            and_(
                step.id == instance.current_step_id,
                step.tenant_id == instance.tenant_id,
            ),
        )
        .join(
            version,
            and_(
                version.id == instance.workflow_version_id,
                version.tenant_id == instance.tenant_id,
            ),
        )
        .join(
            definition,
            and_(
                definition.id == version.definition_id,
                definition.tenant_id == instance.tenant_id,
            ),
        )
        .where(
            instance.tenant_id == actor.tenant_id,
            instance.status == "active",
            step.step_type.in_(("task", "approval")),
        )
    )
    if team:
        return query
    if actor.role == "auditor":
        return query.where(false())
    active_assignment = (
        select(OrganizationUnitAssignment.id)
        .join(
            OrganizationUnit,
            and_(
                OrganizationUnit.id == OrganizationUnitAssignment.unit_id,
                OrganizationUnit.tenant_id == OrganizationUnitAssignment.tenant_id,
            ),
        )
        .where(
            OrganizationUnitAssignment.tenant_id == actor.tenant_id,
            OrganizationUnitAssignment.user_id == actor.user_id,
            OrganizationUnitAssignment.status == "active",
            OrganizationUnit.status == "active",
            OrganizationUnitAssignment.unit_id == assignment.target_organization_unit_id,
        )
        .correlate(assignment)
        .exists()
    )
    eligible = (
        select(assignment.id)
        .where(
            assignment.tenant_id == actor.tenant_id,
            assignment.workflow_version_id == instance.workflow_version_id,
            assignment.step_id == instance.current_step_id,
            or_(
                and_(assignment.target_type == "user", assignment.target_user_id == actor.user_id),
                and_(
                    assignment.target_type == "application_role",
                    assignment.target_application_role == actor.role,
                ),
                and_(assignment.target_type == "organization_unit", active_assignment),
            ),
        )
        .correlate(instance)
        .exists()
    )
    return query.where(eligible)


def capa_query(actor: OrganizationActor, *, team: bool, today: date) -> Select[Any]:
    action, parent = QMSCAPAAction, QMSCAPA
    waiting = action.state == "completed"
    query = (
        projection(
            "capa",
            identifier=action.id,
            unit=action.unit_id,
            title=action.title,
            context=parent.code + " · " + parent.name,
            state=case((waiting, "awaiting_verification"), else_=action.state),
            due=action.due_date,
            assigned=case((waiting, cast(literal(None), Uuid)), else_=action.owner_user_id),
            workspace="capa",
            parent=parent.id,
            child=action.id,
            process=parent.process_id,
            updated=action.updated_at,
            today=today,
            waiting=waiting,
        )
        .select_from(action)
        .join(
            parent,
            and_(
                parent.id == action.capa_id,
                parent.tenant_id == action.tenant_id,
                parent.unit_id == action.unit_id,
            ),
        )
        .where(
            action.tenant_id == actor.tenant_id,
            capability("capa.read", action.unit_id),
            or_(
                parent.source_type == "other",
                and_(parent.source_type == "ncr", capability("ncr.read", parent.unit_id)),
                and_(parent.source_type == "risk", capability("risks.read", parent.unit_id)),
            ),
            or_(
                and_(
                    action.state == "open", parent.state.in_(("action_planned", "implementation"))
                ),
                and_(
                    action.state.in_(("in_progress", "completed")), parent.state == "implementation"
                ),
            ),
        )
    )
    if not team:
        query = query.where(
            or_(
                and_(
                    action.state.in_(("open", "in_progress")),
                    action.owner_user_id == actor.user_id,
                    capability("capa.manage", action.unit_id),
                ),
                and_(
                    waiting,
                    action.completed_by_user_id != actor.user_id,
                    capability("capa.review", action.unit_id),
                ),
            )
        )
    return query


def activity_query(actor: OrganizationActor, *, team: bool, today: date) -> Select[Any]:
    activity, parent = QMSControlInstanceActivity, QMSControlInstance
    query = (
        projection(
            "control_activity",
            identifier=activity.id,
            unit=activity.unit_id,
            title=activity.name,
            context=parent.code + " · " + parent.name,
            state=activity.status,
            due=activity.target_date,
            assigned=activity.assigned_to_user_id,
            workspace="controls",
            parent=parent.id,
            child=activity.id,
            process=parent.process_id,
            updated=activity.updated_at,
            today=today,
        )
        .select_from(activity)
        .join(
            parent,
            and_(
                parent.id == activity.control_instance_id,
                parent.tenant_id == activity.tenant_id,
                parent.unit_id == activity.unit_id,
            ),
        )
        .where(
            activity.tenant_id == actor.tenant_id,
            activity.status != "completed",
            parent.status == "active",
            capability("controls.read", activity.unit_id),
            capability("control_instances.read", activity.unit_id),
        )
    )
    if not team:
        query = query.where(
            activity.assigned_to_user_id == actor.user_id,
            capability("control_instances.manage", activity.unit_id),
        )
    return query


def evidence_query(actor: OrganizationActor, *, team: bool, today: date) -> Select[Any]:
    evidence, parent = QMSControlInstanceEvidence, QMSControlInstance
    query = (
        projection(
            "evidence_review",
            identifier=evidence.id,
            unit=evidence.unit_id,
            title=literal("Review evidence: ") + evidence.name,
            context=parent.code + " · " + parent.name,
            state=evidence.status,
            due=cast(literal(None), Date),
            assigned=cast(literal(None), Uuid),
            workspace="controls",
            parent=parent.id,
            child=evidence.id,
            process=parent.process_id,
            updated=evidence.updated_at,
            today=today,
            waiting=True,
        )
        .select_from(evidence)
        .join(
            parent,
            and_(
                parent.id == evidence.control_instance_id,
                parent.tenant_id == evidence.tenant_id,
                parent.unit_id == evidence.unit_id,
            ),
        )
        .where(
            evidence.tenant_id == actor.tenant_id,
            evidence.status == "submitted",
            parent.status == "active",
            capability("controls.read", evidence.unit_id),
            capability("control_instances.read", evidence.unit_id),
        )
    )
    if not team:
        query = query.where(
            evidence.submitted_by_user_id != actor.user_id,
            capability("control_instances.manage", evidence.unit_id),
            capability("evidence.review", evidence.unit_id),
        )
    return query


def queue_statement(
    actor: OrganizationActor, *, team: bool, today: date, unit_id: UUID | None, limit: int
) -> Select[Any]:
    queries = [
        workflow_query(actor, team=team, today=today),
        capa_query(actor, team=team, today=today),
        activity_query(actor, team=team, today=today),
        evidence_query(actor, team=team, today=today),
    ]
    combined = queries[0].union_all(*queries[1:]).subquery("candidates")
    eligible = select(combined)
    if unit_id is not None:
        # Workflow has no business-unit scope; assignment units are not resource scopes.
        eligible = eligible.where(combined.c.unit_id == unit_id)
    rows = eligible.cte("eligible")
    counts = select(rows.c.source, func.count().label("total")).group_by(rows.c.source).subquery()
    by_source = select(
        func.coalesce(
            func.jsonb_object_agg(counts.c.source, counts.c.total), literal("{}").cast(JSONB)
        )
    ).scalar_subquery()
    summary = (
        select(
            func.count().label("total"),
            func.count().filter(rows.c.overdue).label("overdue_count"),
            func.count().filter(rows.c.urgency == "due_soon").label("due_soon_count"),
            func.count().filter(rows.c.assigned_to_user_id.is_(None)).label("unassigned_count"),
            by_source.label("by_source"),
        )
        .select_from(rows)
        .subquery("summary")
    )
    rank = case(
        (rows.c.urgency == "overdue", 0),
        (rows.c.urgency == "waiting_review", 1),
        (rows.c.urgency == "due_soon", 2),
        else_=3,
    )
    page = (
        select(rows)
        .order_by(
            rank,
            func.coalesce(rows.c.due_date, date.max),
            rows.c.updated_at.desc(),
            rows.c.id,
        )
        .limit(limit)
        .subquery("page")
    )
    return (
        select(page, summary)
        .select_from(summary.outerjoin(page, literal(True)))
        .order_by(
            case(
                (page.c.urgency == "overdue", 0),
                (page.c.urgency == "waiting_review", 1),
                (page.c.urgency == "due_soon", 2),
                else_=3,
            ),
            func.coalesce(page.c.due_date, date.max),
            page.c.updated_at.desc(),
            page.c.id,
        )
    )
