from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db, set_request_context
from pmc_api.models import OrganizationUnit, OrganizationUnitAssignment, User
from pmc_api.organization_service import (
    OrganizationActor,
    archive_unit,
    create_assignment,
    create_unit,
    list_assignments,
    list_units,
    move_unit,
    require_context,
    restore_unit,
    update_assignment,
    update_unit,
)

router = APIRouter(prefix="/organization", tags=["organization"])
DBSession = Annotated[Session, Depends(get_db)]


class UnitInput(BaseModel):
    unit_type: str = Field(pattern="^(site|department|team)$")
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    parent_id: UUID | None = None


class UnitPatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)


class MoveInput(BaseModel):
    parent_id: UUID | None = None


class AssignmentInput(BaseModel):
    unit_id: UUID
    user_id: UUID
    assignment_role: str = Field(pattern="^(member|lead)$")
    is_primary: bool = False


class AssignmentPatch(BaseModel):
    assignment_role: str | None = Field(default=None, pattern="^(member|lead)$")
    is_primary: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class UnitResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_id: UUID | None
    unit_type: str
    code: str
    name: str
    description: str | None
    status: str
    model_config = {"from_attributes": True}


class AssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    user_id: UUID
    assignment_role: str
    is_primary: bool
    status: str
    user_display_name: str | None = None
    model_config = {"from_attributes": True}


def _actor(db: Session, authenticated: Authenticated) -> OrganizationActor:
    actor = require_context(
        db, user_id=authenticated.user.id, tenant_id=authenticated.record.current_tenant_id
    )
    set_request_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    return actor


def _unit_or_404(db: Session, actor: OrganizationActor, unit_id: UUID) -> OrganizationUnit:
    unit = db.scalar(
        select(OrganizationUnit).where(
            OrganizationUnit.id == unit_id, OrganizationUnit.tenant_id == actor.tenant_id
        )
    )
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "organization unit not found")
    return unit


def _assignment_or_404(
    db: Session, actor: OrganizationActor, assignment_id: UUID
) -> OrganizationUnitAssignment:
    assignment = db.scalar(
        select(OrganizationUnitAssignment).where(
            OrganizationUnitAssignment.id == assignment_id,
            OrganizationUnitAssignment.tenant_id == actor.tenant_id,
        )
    )
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "organization assignment not found")
    return assignment


def _conflict(exc: IntegrityError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "organization constraint rejected the change")


def _assignment_response(db: Session, assignment: OrganizationUnitAssignment) -> dict[str, object]:
    user = db.get(User, assignment.user_id)
    return {
        "id": assignment.id,
        "tenant_id": assignment.tenant_id,
        "unit_id": assignment.unit_id,
        "user_id": assignment.user_id,
        "assignment_role": assignment.assignment_role,
        "is_primary": assignment.is_primary,
        "status": assignment.status,
        "user_display_name": user.display_name if user else None,
    }


@router.get("/units", response_model=list[UnitResponse])
def get_units(
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[OrganizationUnit]:
    return list_units(db, _actor(db, authenticated), limit=limit, offset=offset)


@router.post(
    "/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def post_unit(
    request: Request, body: UnitInput, db: DBSession, authenticated: Authenticated
) -> OrganizationUnit:
    try:
        return create_unit(
            db,
            actor=_actor(db, authenticated),
            request_id=request.state.request_id,
            values=body.model_dump(),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.get("/units/{unit_id}", response_model=UnitResponse)
def get_unit(unit_id: UUID, db: DBSession, authenticated: Authenticated) -> OrganizationUnit:
    return _unit_or_404(db, _actor(db, authenticated), unit_id)


@router.patch("/units/{unit_id}", response_model=UnitResponse, dependencies=[Depends(require_csrf)])
def patch_unit(
    request: Request, unit_id: UUID, body: UnitPatch, db: DBSession, authenticated: Authenticated
) -> OrganizationUnit:
    actor = _actor(db, authenticated)
    try:
        return update_unit(
            db,
            actor=actor,
            request_id=request.state.request_id,
            unit=_unit_or_404(db, actor, unit_id),
            changes=body.model_dump(exclude_unset=True),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/units/{unit_id}/move", response_model=UnitResponse, dependencies=[Depends(require_csrf)]
)
def post_move(
    request: Request, unit_id: UUID, body: MoveInput, db: DBSession, authenticated: Authenticated
) -> OrganizationUnit:
    actor = _actor(db, authenticated)
    try:
        return move_unit(
            db,
            actor=actor,
            request_id=request.state.request_id,
            unit=_unit_or_404(db, actor, unit_id),
            parent_id=body.parent_id,
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/units/{unit_id}/archive", response_model=UnitResponse, dependencies=[Depends(require_csrf)]
)
def post_archive(
    request: Request, unit_id: UUID, db: DBSession, authenticated: Authenticated
) -> OrganizationUnit:
    actor = _actor(db, authenticated)
    try:
        return archive_unit(
            db,
            actor=actor,
            request_id=request.state.request_id,
            unit=_unit_or_404(db, actor, unit_id),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/units/{unit_id}/restore", response_model=UnitResponse, dependencies=[Depends(require_csrf)]
)
def post_restore(
    request: Request, unit_id: UUID, db: DBSession, authenticated: Authenticated
) -> OrganizationUnit:
    actor = _actor(db, authenticated)
    try:
        return restore_unit(
            db,
            actor=actor,
            request_id=request.state.request_id,
            unit=_unit_or_404(db, actor, unit_id),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.get("/assignments", response_model=list[AssignmentResponse])
def get_assignments(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[dict[str, object]]:
    return [
        _assignment_response(db, row)
        for row in list_assignments(
            db, _actor(db, authenticated), limit=limit, offset=offset, unit_id=unit_id
        )
    ]


@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def post_assignment(
    request: Request, body: AssignmentInput, db: DBSession, authenticated: Authenticated
) -> dict[str, object]:
    try:
        return _assignment_response(
            db,
            create_assignment(
                db,
                actor=_actor(db, authenticated),
                request_id=request.state.request_id,
                values=body.model_dump(),
            ),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc


@router.patch(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    dependencies=[Depends(require_csrf)],
)
def patch_assignment(
    request: Request,
    assignment_id: UUID,
    body: AssignmentPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> dict[str, object]:
    actor = _actor(db, authenticated)
    try:
        return _assignment_response(
            db,
            update_assignment(
                db,
                actor=actor,
                request_id=request.state.request_id,
                assignment=_assignment_or_404(db, actor, assignment_id),
                changes=body.model_dump(exclude_unset=True),
            ),
        )
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from exc
