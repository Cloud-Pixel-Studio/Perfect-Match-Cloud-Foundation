from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db, set_request_context
from pmc_api.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceEvent,
    WorkflowStep,
    WorkflowStepAssignment,
    WorkflowTransition,
    WorkflowVersion,
)
from pmc_api.workflow_service import (
    WorkflowActor,
    cancel_instance,
    create_definition,
    create_version,
    publish_version,
    require_context,
    start_instance,
    transition_instance,
    update_definition,
    upsert_assignment,
    upsert_step,
    upsert_transition,
)

router = APIRouter(tags=["workflow"])
DBSession = Annotated[Session, Depends(get_db)]


class DefinitionInput(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)


class DefinitionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|retired)$")


class StepInput(BaseModel):
    step_key: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    step_type: str = Field(pattern="^(task|approval|end)$")
    is_start: bool = False
    position: int = Field(ge=0, le=10000)


class TransitionInput(BaseModel):
    from_step_id: UUID
    to_step_id: UUID
    transition_key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=160)


class AssignmentInput(BaseModel):
    step_id: UUID
    target_type: str = Field(pattern="^(user|organization_unit|application_role)$")
    target_user_id: UUID | None = None
    target_organization_unit_id: UUID | None = None
    target_application_role: str | None = Field(default=None, pattern="^(owner|admin|member)$")


class InstanceInput(BaseModel):
    workflow_version_id: UUID
    title: str = Field(min_length=1, max_length=200)
    reference: str | None = Field(default=None, max_length=200)


class TransitionCommand(BaseModel):
    transition_id: UUID
    expected_version: int = Field(ge=1)


class Row(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DefinitionResponse(Row):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    description: str | None
    status: str


class VersionResponse(Row):
    id: UUID
    tenant_id: UUID
    definition_id: UUID
    version_number: int
    status: str


class StepResponse(Row):
    id: UUID
    tenant_id: UUID
    workflow_version_id: UUID
    step_key: str
    name: str
    description: str | None
    step_type: str
    is_start: bool
    position: int


class TransitionResponse(Row):
    id: UUID
    tenant_id: UUID
    workflow_version_id: UUID
    from_step_id: UUID
    to_step_id: UUID
    transition_key: str
    label: str


class EventResponse(Row):
    id: UUID
    tenant_id: UUID
    instance_id: UUID
    event_type: str
    from_step_id: UUID | None
    to_step_id: UUID | None
    transition_id: UUID | None
    actor_user_id: UUID
    request_id: UUID
    occurred_at: datetime
    event_metadata: dict[str, object]


class AssignmentResponse(Row):
    id: UUID
    tenant_id: UUID
    workflow_version_id: UUID
    step_id: UUID
    target_type: str
    target_user_id: UUID | None
    target_organization_unit_id: UUID | None
    target_application_role: str | None


class InstanceResponse(Row):
    id: UUID
    workflow_version_id: UUID
    title: str
    reference: str | None
    status: str
    current_step_id: UUID
    row_version: int
    started_at: datetime


def _actor(request: Request, db: Session, authenticated: Authenticated) -> WorkflowActor:
    actor = require_context(
        db, user_id=authenticated.user.id, tenant_id=authenticated.record.current_tenant_id
    )
    set_request_context(
        db,
        user_id=actor.user_id,
        tenant_id=actor.tenant_id,
        session_hash=authenticated.record.token_hash,
    )
    return actor


def _owned(db: Session, model: Any, row_id: UUID, tenant_id: UUID) -> Any:
    row = db.scalar(select(model).where(model.id == row_id, model.tenant_id == tenant_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow resource not found")
    return row


@router.get("/workflows", response_model=list[DefinitionResponse])
def definitions(
    request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowDefinition]:
    actor = _actor(request, db, authenticated)
    return list(
        db.scalars(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.tenant_id == actor.tenant_id)
            .order_by(WorkflowDefinition.name)
            .limit(100)
        )
    )


@router.post(
    "/workflows",
    response_model=DefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create(
    request: Request, body: DefinitionInput, db: DBSession, authenticated: Authenticated
) -> WorkflowDefinition:
    return create_definition(
        db, _actor(request, db, authenticated), request.state.request_id, **body.model_dump()
    )


@router.patch(
    "/workflows/{workflow_id}",
    response_model=DefinitionResponse,
    dependencies=[Depends(require_csrf)],
)
def update(
    workflow_id: UUID,
    request: Request,
    body: DefinitionPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowDefinition:
    actor = _actor(request, db, authenticated)
    row = _owned(db, WorkflowDefinition, workflow_id, actor.tenant_id)
    return update_definition(
        db, actor, request.state.request_id, row, body.model_dump(exclude_unset=True)
    )


@router.get("/workflows/{workflow_id}/versions", response_model=list[VersionResponse])
def versions(
    workflow_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowVersion]:
    actor = _actor(request, db, authenticated)
    _owned(db, WorkflowDefinition, workflow_id, actor.tenant_id)
    return list(
        db.scalars(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.tenant_id == actor.tenant_id,
                WorkflowVersion.definition_id == workflow_id,
            )
            .order_by(WorkflowVersion.version_number.desc())
        )
    )


@router.post(
    "/workflows/{workflow_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def new_version(
    workflow_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> WorkflowVersion:
    actor = _actor(request, db, authenticated)
    definition = _owned(db, WorkflowDefinition, workflow_id, actor.tenant_id)
    return create_version(db, actor, request.state.request_id, definition)


@router.get("/workflows/versions/{version_id}", response_model=VersionResponse)
def version_detail(
    version_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> WorkflowVersion:
    actor = _actor(request, db, authenticated)
    return cast(WorkflowVersion, _owned(db, WorkflowVersion, version_id, actor.tenant_id))


@router.get("/workflows/versions/{version_id}/steps", response_model=list[StepResponse])
def steps(
    version_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowStep]:
    actor = _actor(request, db, authenticated)
    _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return list(
        db.scalars(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_version_id == version_id)
            .order_by(WorkflowStep.position)
        )
    )


@router.get("/workflows/versions/{version_id}/transitions", response_model=list[TransitionResponse])
def transitions(
    version_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowTransition]:
    actor = _actor(request, db, authenticated)
    _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return list(
        db.scalars(
            select(WorkflowTransition)
            .where(WorkflowTransition.workflow_version_id == version_id)
            .order_by(WorkflowTransition.transition_key)
        )
    )


@router.post(
    "/workflows/versions/{version_id}/steps",
    response_model=StepResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_step(
    version_id: UUID, request: Request, body: StepInput, db: DBSession, authenticated: Authenticated
) -> WorkflowStep:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return upsert_step(db, actor, request.state.request_id, version, None, body.model_dump())


@router.patch(
    "/workflows/versions/{version_id}/steps/{step_id}",
    response_model=StepResponse,
    dependencies=[Depends(require_csrf)],
)
def edit_step(
    version_id: UUID,
    step_id: UUID,
    request: Request,
    body: StepInput,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowStep:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return upsert_step(db, actor, request.state.request_id, version, step_id, body.model_dump())


@router.post(
    "/workflows/versions/{version_id}/transitions",
    response_model=TransitionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_transition(
    version_id: UUID,
    request: Request,
    body: TransitionInput,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowTransition:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return upsert_transition(db, actor, request.state.request_id, version, None, body.model_dump())


@router.patch(
    "/workflows/versions/{version_id}/transitions/{transition_id}",
    response_model=TransitionResponse,
    dependencies=[Depends(require_csrf)],
)
def edit_transition(
    version_id: UUID,
    transition_id: UUID,
    request: Request,
    body: TransitionInput,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowTransition:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return upsert_transition(
        db, actor, request.state.request_id, version, transition_id, body.model_dump()
    )


@router.post(
    "/workflows/versions/{version_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_assignment(
    version_id: UUID,
    request: Request,
    body: AssignmentInput,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowStepAssignment:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return upsert_assignment(db, actor, request.state.request_id, version, None, body.model_dump())


@router.post(
    "/workflows/versions/{version_id}/publish",
    response_model=VersionResponse,
    dependencies=[Depends(require_csrf)],
)
def publish(
    version_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> WorkflowVersion:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, version_id, actor.tenant_id)
    return publish_version(db, actor, request.state.request_id, version)


@router.get("/workflow-instances", response_model=list[InstanceResponse])
def instances(
    request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowInstance]:
    actor = _actor(request, db, authenticated)
    return list(
        db.scalars(
            select(WorkflowInstance)
            .where(WorkflowInstance.tenant_id == actor.tenant_id)
            .order_by(WorkflowInstance.updated_at.desc())
            .limit(100)
        )
    )


@router.get("/workflow-instances/{instance_id}", response_model=InstanceResponse)
def instance(
    instance_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> WorkflowInstance:
    actor = _actor(request, db, authenticated)
    return cast(WorkflowInstance, _owned(db, WorkflowInstance, instance_id, actor.tenant_id))


@router.post(
    "/workflow-instances",
    response_model=InstanceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def start(
    request: Request, body: InstanceInput, db: DBSession, authenticated: Authenticated
) -> WorkflowInstance:
    actor = _actor(request, db, authenticated)
    version = _owned(db, WorkflowVersion, body.workflow_version_id, actor.tenant_id)
    return start_instance(db, actor, request.state.request_id, version, body.title, body.reference)


@router.post(
    "/workflow-instances/{instance_id}/transition",
    response_model=InstanceResponse,
    dependencies=[Depends(require_csrf)],
)
def transition(
    instance_id: UUID,
    request: Request,
    body: TransitionCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> WorkflowInstance:
    actor = _actor(request, db, authenticated)
    row = _owned(db, WorkflowInstance, instance_id, actor.tenant_id)
    return transition_instance(
        db, actor, request.state.request_id, row, body.transition_id, body.expected_version
    )


@router.post(
    "/workflow-instances/{instance_id}/cancel",
    response_model=InstanceResponse,
    dependencies=[Depends(require_csrf)],
)
def cancel(
    instance_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> WorkflowInstance:
    actor = _actor(request, db, authenticated)
    row = _owned(db, WorkflowInstance, instance_id, actor.tenant_id)
    return cancel_instance(db, actor, request.state.request_id, row)


@router.get("/workflow-instances/{instance_id}/history", response_model=list[EventResponse])
def history(
    instance_id: UUID, request: Request, db: DBSession, authenticated: Authenticated
) -> list[WorkflowInstanceEvent]:
    actor = _actor(request, db, authenticated)
    _owned(db, WorkflowInstance, instance_id, actor.tenant_id)
    return list(
        db.scalars(
            select(WorkflowInstanceEvent)
            .where(
                WorkflowInstanceEvent.instance_id == instance_id,
                WorkflowInstanceEvent.tenant_id == actor.tenant_id,
            )
            .order_by(WorkflowInstanceEvent.occurred_at, WorkflowInstanceEvent.id)
        )
    )
