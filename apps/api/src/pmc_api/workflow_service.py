from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.models import (
    Membership,
    OrganizationUnit,
    OrganizationUnitAssignment,
    User,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceEvent,
    WorkflowStep,
    WorkflowStepAssignment,
    WorkflowTransition,
    WorkflowVersion,
)


@dataclass(frozen=True)
class WorkflowActor:
    user_id: UUID
    display_name: str
    role: str
    tenant_id: UUID


def require_context(db: Session, *, user_id: UUID, tenant_id: UUID | None) -> WorkflowActor:
    if tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tenant selection required")
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
            Membership.status == "active",
        )
    )
    user = db.get(User, user_id)
    if membership is None or user is None or user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant access denied")
    return WorkflowActor(user.id, user.display_name, membership.role, tenant_id)


def _write(actor: WorkflowActor) -> None:
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "workflow configuration requires owner or admin"
        )


def _now() -> datetime:
    return datetime.now(UTC)


def _definition_values(row: WorkflowDefinition) -> dict[str, object]:
    return {"workflow_definition_id": str(row.id), "status": row.status}


def _version_values(row: WorkflowVersion) -> dict[str, object]:
    return {
        "workflow_version_id": str(row.id),
        "workflow_definition_id": str(row.definition_id),
        "version_number": row.version_number,
        "status": row.status,
    }


def _instance_values(row: WorkflowInstance) -> dict[str, object]:
    return {
        "workflow_instance_id": str(row.id),
        "workflow_version_id": str(row.workflow_version_id),
        "to_step_id": str(row.current_step_id),
        "status": row.status,
        "row_version": row.row_version,
    }


def _step_values(row: WorkflowStep) -> dict[str, object]:
    return {
        "step_id": str(row.id),
        "workflow_version_id": str(row.workflow_version_id),
        "step_key": row.step_key,
        "name": row.name,
        "step_type": row.step_type,
        "is_start": row.is_start,
        "position": row.position,
    }


def _transition_values(row: WorkflowTransition) -> dict[str, object]:
    return {
        "transition_id": str(row.id),
        "workflow_version_id": str(row.workflow_version_id),
        "from_step_id": str(row.from_step_id),
        "to_step_id": str(row.to_step_id),
        "transition_key": row.transition_key,
        "label": row.label,
    }


def _assignment_values(row: WorkflowStepAssignment) -> dict[str, object]:
    return {
        "assignment_id": str(row.id),
        "workflow_version_id": str(row.workflow_version_id),
        "step_id": str(row.step_id),
        "target_type": row.target_type,
        "target_user_id": str(row.target_user_id) if row.target_user_id else None,
        "target_organization_unit_id": (
            str(row.target_organization_unit_id) if row.target_organization_unit_id else None
        ),
        "target_application_role": row.target_application_role,
    }


def _audit(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    action: str,
    resource_id: UUID,
    old: dict[str, object] | None,
    new: dict[str, object] | None,
) -> None:
    writers = {
        "workflow.definition_created": audit_service.record_workflow_definition_created,
        "workflow.definition_updated": audit_service.record_workflow_definition_updated,
        "workflow.definition_retired": audit_service.record_workflow_definition_retired,
        "workflow.version_created": audit_service.record_workflow_version_created,
        "workflow.version_updated": audit_service.record_workflow_version_updated,
        "workflow.version_published": audit_service.record_workflow_version_published,
        "workflow.step_created": audit_service.record_workflow_step_created,
        "workflow.step_updated": audit_service.record_workflow_step_updated,
        "workflow.transition_created": audit_service.record_workflow_transition_created,
        "workflow.transition_updated": audit_service.record_workflow_transition_updated,
        "workflow.assignment_created": audit_service.record_workflow_assignment_created,
        "workflow.assignment_updated": audit_service.record_workflow_assignment_updated,
        "workflow.instance_started": audit_service.record_workflow_instance_started,
        "workflow.instance_transitioned": audit_service.record_workflow_instance_transitioned,
        "workflow.instance_completed": audit_service.record_workflow_instance_completed,
        "workflow.instance_cancelled": audit_service.record_workflow_instance_cancelled,
    }
    writers[action](
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        resource_id=resource_id,
        request_id=request_id,
        old_values=old,
        new_values=new,
    )


def create_definition(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    code: str,
    name: str,
    description: str | None,
) -> WorkflowDefinition:
    _write(actor)
    if db.scalar(
        select(WorkflowDefinition.id).where(
            WorkflowDefinition.tenant_id == actor.tenant_id,
            WorkflowDefinition.code.ilike(code.strip()),
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "workflow definition code already exists")
    now = _now()
    row = WorkflowDefinition(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        code=code.strip(),
        name=name.strip(),
        description=description,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            "workflow.definition_created",
            row.id,
            None,
            _definition_values(row),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def update_definition(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    row: WorkflowDefinition,
    changes: dict[str, object],
) -> WorkflowDefinition:
    _write(actor)
    before = _definition_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = _now()
    try:
        db.flush()
        action = (
            "workflow.definition_retired"
            if row.status == "retired"
            else "workflow.definition_updated"
        )
        _audit(db, actor, request_id, action, row.id, before, _definition_values(row))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def create_version(
    db: Session, actor: WorkflowActor, request_id: UUID, definition: WorkflowDefinition
) -> WorkflowVersion:
    _write(actor)
    if db.scalar(
        select(WorkflowVersion.id).where(
            WorkflowVersion.definition_id == definition.id,
            WorkflowVersion.status == "draft",
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "workflow definition already has a draft version"
        )
    latest = db.scalar(
        select(WorkflowVersion.version_number)
        .where(WorkflowVersion.definition_id == definition.id)
        .order_by(WorkflowVersion.version_number.desc())
        .limit(1)
    )
    now = _now()
    row = WorkflowVersion(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        definition_id=definition.id,
        version_number=(latest or 0) + 1,
        status="draft",
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _audit(
            db, actor, request_id, "workflow.version_created", row.id, None, _version_values(row)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def _draft(row: WorkflowVersion) -> None:
    if row.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "published workflow versions are immutable")


def upsert_step(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    version: WorkflowVersion,
    step_id: UUID | None,
    values: dict[str, object],
) -> WorkflowStep:
    _write(actor)
    _draft(version)
    now = _now()
    row = db.get(WorkflowStep, step_id) if step_id else None
    before = _step_values(row) if row is not None else None
    if row is None:
        row = WorkflowStep(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            workflow_version_id=version.id,
            created_at=now,
            updated_at=now,
            **values,
        )
        db.add(row)
    else:
        if row.workflow_version_id != version.id or row.tenant_id != actor.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow step not found")
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            "workflow.step_updated" if step_id else "workflow.step_created",
            row.id,
            before,
            _step_values(row),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def upsert_transition(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    version: WorkflowVersion,
    transition_id: UUID | None,
    values: dict[str, object],
) -> WorkflowTransition:
    _write(actor)
    _draft(version)
    now = _now()
    row = db.get(WorkflowTransition, transition_id) if transition_id else None
    before = _transition_values(row) if row is not None else None
    if row is None:
        row = WorkflowTransition(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            workflow_version_id=version.id,
            created_at=now,
            updated_at=now,
            **values,
        )
        db.add(row)
    else:
        if row.workflow_version_id != version.id or row.tenant_id != actor.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow transition not found")
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            "workflow.transition_updated" if transition_id else "workflow.transition_created",
            row.id,
            before,
            _transition_values(row),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def upsert_assignment(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    version: WorkflowVersion,
    assignment_id: UUID | None,
    values: dict[str, object],
) -> WorkflowStepAssignment:
    _write(actor)
    _draft(version)
    now = _now()
    row = db.get(WorkflowStepAssignment, assignment_id) if assignment_id else None
    before = _assignment_values(row) if row is not None else None
    if row is None:
        row = WorkflowStepAssignment(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            workflow_version_id=version.id,
            created_at=now,
            updated_at=now,
            **values,
        )
        db.add(row)
    else:
        if row.workflow_version_id != version.id or row.tenant_id != actor.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow assignment not found")
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            "workflow.assignment_updated" if assignment_id else "workflow.assignment_created",
            row.id,
            before,
            _assignment_values(row),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def _validate_graph(db: Session, version: WorkflowVersion) -> None:
    steps = list(
        db.scalars(select(WorkflowStep).where(WorkflowStep.workflow_version_id == version.id))
    )
    transitions = list(
        db.scalars(
            select(WorkflowTransition).where(WorkflowTransition.workflow_version_id == version.id)
        )
    )
    assignments = list(
        db.scalars(
            select(WorkflowStepAssignment).where(
                WorkflowStepAssignment.workflow_version_id == version.id
            )
        )
    )
    if len([s for s in steps if s.is_start]) != 1 or not any(s.step_type == "end" for s in steps):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a workflow requires exactly one start and at least one end"
        )
    ids = {s.id for s in steps}
    start = next(s for s in steps if s.is_start)
    outgoing: dict[UUID, set[UUID]] = {s.id: set() for s in steps}
    incoming: dict[UUID, set[UUID]] = {s.id: set() for s in steps}
    for edge in transitions:
        if edge.from_step_id not in ids or edge.to_step_id not in ids:
            raise HTTPException(status.HTTP_409_CONFLICT, "transition references a foreign step")
        outgoing[edge.from_step_id].add(edge.to_step_id)
        incoming[edge.to_step_id].add(edge.from_step_id)
    if any(s.step_type == "end" and outgoing[s.id] for s in steps):
        raise HTTPException(status.HTTP_409_CONFLICT, "end steps cannot have outgoing transitions")
    reachable = {start.id}
    pending = [start.id]
    while pending:
        current = pending.pop()
        for target in outgoing[current]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    if reachable != ids:
        raise HTTPException(status.HTTP_409_CONFLICT, "every step must be reachable from the start")
    can_end = {s.id for s in steps if s.step_type == "end"}
    pending = list(can_end)
    while pending:
        current = pending.pop()
        for source in incoming[current]:
            if source not in can_end:
                can_end.add(source)
                pending.append(source)
    if any(s.id not in can_end for s in steps):
        raise HTTPException(status.HTTP_409_CONFLICT, "every path must reach an end step")
    assigned = {a.step_id for a in assignments}
    if any(s.step_type in {"task", "approval"} and s.id not in assigned for s in steps):
        raise HTTPException(status.HTTP_409_CONFLICT, "actionable steps require an assignment")
    for assignment in assignments:
        valid_target = False
        if assignment.target_type == "user":
            valid_target = (
                db.scalar(
                    text(
                        "SELECT user_id FROM organization_member_directory() "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": assignment.target_user_id},
                )
                is not None
            )
        elif assignment.target_type == "organization_unit":
            valid_target = (
                db.scalar(
                    select(OrganizationUnit.id).where(
                        OrganizationUnit.id == assignment.target_organization_unit_id,
                        OrganizationUnit.tenant_id == version.tenant_id,
                        OrganizationUnit.status == "active",
                    )
                )
                is not None
            )
        else:
            valid_target = assignment.target_application_role in {"owner", "admin", "member"}
        if not valid_target:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "assignment target must be active and tenant-scoped"
            )


def publish_version(
    db: Session, actor: WorkflowActor, request_id: UUID, version: WorkflowVersion
) -> WorkflowVersion:
    _write(actor)
    _draft(version)
    _validate_graph(db, version)
    version.status = "published"
    version.published_at = _now()
    version.updated_at = _now()
    try:
        db.flush()
        _audit(
            db,
            actor,
            request_id,
            "workflow.version_published",
            version.id,
            {"status": "draft"},
            _version_values(version),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return version


def _eligible(db: Session, actor: WorkflowActor, step_id: UUID, version_id: UUID) -> bool:
    assignments = list(
        db.scalars(
            select(WorkflowStepAssignment).where(
                WorkflowStepAssignment.step_id == step_id,
                WorkflowStepAssignment.workflow_version_id == version_id,
                WorkflowStepAssignment.tenant_id == actor.tenant_id,
            )
        )
    )
    for assignment in assignments:
        if assignment.target_type == "user" and assignment.target_user_id == actor.user_id:
            return True
        if (
            assignment.target_type == "application_role"
            and assignment.target_application_role == actor.role
        ):
            return True
        if assignment.target_type == "organization_unit":
            active_unit = db.scalar(
                select(OrganizationUnit.id).where(
                    OrganizationUnit.id == assignment.target_organization_unit_id,
                    OrganizationUnit.tenant_id == actor.tenant_id,
                    OrganizationUnit.status == "active",
                )
            )
            member = db.scalar(
                select(OrganizationUnitAssignment.id).where(
                    OrganizationUnitAssignment.unit_id == assignment.target_organization_unit_id,
                    OrganizationUnitAssignment.user_id == actor.user_id,
                    OrganizationUnitAssignment.tenant_id == actor.tenant_id,
                    OrganizationUnitAssignment.status == "active",
                )
            )
            if active_unit and member:
                return True
    return False


def eligible_actions(
    db: Session, actor: WorkflowActor, row: WorkflowInstance
) -> list[WorkflowTransition]:
    if row.status != "active" or actor.role == "auditor":
        return []
    transitions = list(
        db.scalars(
            select(WorkflowTransition)
            .where(
                WorkflowTransition.tenant_id == actor.tenant_id,
                WorkflowTransition.workflow_version_id == row.workflow_version_id,
                WorkflowTransition.from_step_id == row.current_step_id,
            )
            .order_by(WorkflowTransition.transition_key, WorkflowTransition.id)
            .limit(100)
        )
    )
    if not _eligible(db, actor, row.current_step_id, row.workflow_version_id):
        return []
    return transitions


def start_instance(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    version: WorkflowVersion,
    title: str,
    reference: str | None,
) -> WorkflowInstance:
    _write(actor)
    if version.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "instances require a published version")
    start = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.workflow_version_id == version.id, WorkflowStep.is_start.is_(True)
        )
    )
    if start is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "published version has no start step")
    now = _now()
    row = WorkflowInstance(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        workflow_version_id=version.id,
        title=title.strip(),
        reference=reference,
        status="active",
        current_step_id=start.id,
        row_version=1,
        started_by_user_id=actor.user_id,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    db.add(
        WorkflowInstanceEvent(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            instance_id=row.id,
            workflow_version_id=version.id,
            event_type="started",
            to_step_id=start.id,
            actor_user_id=actor.user_id,
            request_id=request_id,
            occurred_at=now,
            event_metadata={"row_version": 1},
        )
    )
    try:
        _audit(
            db, actor, request_id, "workflow.instance_started", row.id, None, _instance_values(row)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def transition_instance(
    db: Session,
    actor: WorkflowActor,
    request_id: UUID,
    row: WorkflowInstance,
    transition_id: UUID,
    expected_version: int,
) -> WorkflowInstance:
    if actor.role == "auditor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "auditors have read-only workflow access")
    locked = db.scalar(
        select(WorkflowInstance)
        .where(WorkflowInstance.id == row.id, WorkflowInstance.tenant_id == actor.tenant_id)
        .with_for_update()
    )
    if locked is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow instance not found")
    if locked.row_version != expected_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "stale workflow instance version")
    if locked.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "workflow instance is no longer active")
    edge = db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.id == transition_id,
            WorkflowTransition.workflow_version_id == locked.workflow_version_id,
            WorkflowTransition.from_step_id == locked.current_step_id,
        )
    )
    if edge is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "transition is not valid for the current step"
        )
    if not _eligible(db, actor, locked.current_step_id, locked.workflow_version_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "actor is not assigned to the current step")
    before = _instance_values(locked)
    destination = db.get(WorkflowStep, edge.to_step_id)
    if destination is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "transition destination is missing")
    now = _now()
    locked.current_step_id = destination.id
    locked.row_version += 1
    locked.updated_at = now
    db.add(
        WorkflowInstanceEvent(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            instance_id=locked.id,
            workflow_version_id=locked.workflow_version_id,
            event_type="transitioned",
            from_step_id=edge.from_step_id,
            to_step_id=edge.to_step_id,
            transition_id=edge.id,
            actor_user_id=actor.user_id,
            request_id=request_id,
            occurred_at=now,
            event_metadata={"row_version": locked.row_version},
        )
    )
    try:
        _audit(
            db,
            actor,
            request_id,
            "workflow.instance_transitioned",
            locked.id,
            before,
            _instance_values(locked),
        )
        if destination.step_type == "end":
            locked.status = "completed"
            locked.completed_at = now
            db.add(
                WorkflowInstanceEvent(
                    id=uuid4(),
                    tenant_id=actor.tenant_id,
                    instance_id=locked.id,
                    workflow_version_id=locked.workflow_version_id,
                    event_type="completed",
                    from_step_id=edge.from_step_id,
                    to_step_id=edge.to_step_id,
                    transition_id=edge.id,
                    actor_user_id=actor.user_id,
                    request_id=request_id,
                    occurred_at=now,
                    event_metadata={"row_version": locked.row_version},
                )
            )
            _audit(
                db,
                actor,
                request_id,
                "workflow.instance_completed",
                locked.id,
                before,
                _instance_values(locked),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return locked


def cancel_instance(
    db: Session, actor: WorkflowActor, request_id: UUID, row: WorkflowInstance, reason: str
) -> WorkflowInstance:
    _write(actor)
    locked = db.scalar(
        select(WorkflowInstance)
        .where(WorkflowInstance.id == row.id, WorkflowInstance.tenant_id == actor.tenant_id)
        .with_for_update()
    )
    if locked is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow instance not found")
    if locked.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "workflow instance is no longer active")
    reason = reason.strip()
    if not 1 <= len(reason) <= 500:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "cancellation reason must be 1 to 500 characters"
        )
    before = _instance_values(locked)
    now = _now()
    locked.status = "cancelled"
    locked.cancelled_at = now
    locked.row_version += 1
    locked.updated_at = now
    db.add(
        WorkflowInstanceEvent(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            instance_id=locked.id,
            workflow_version_id=locked.workflow_version_id,
            event_type="cancelled",
            actor_user_id=actor.user_id,
            request_id=request_id,
            occurred_at=now,
            event_metadata={"row_version": locked.row_version},
            reason=reason,
        )
    )
    try:
        _audit(
            db,
            actor,
            request_id,
            "workflow.instance_cancelled",
            locked.id,
            before,
            _instance_values(locked),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return locked
