"""Persisted, scoped planning. Reported work always remains unverified."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from importlib.resources import files
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import QMSProject, QMSProjectStep
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/qms-projects", tags=["qms-projects"], dependencies=[Depends(_no_store)])
DBSession = Annotated[Session, Depends(get_db)]
# Scoped project text contract: Python3.12 whitespace plus BOM, matching the client/DB.
_PROJECT_TEXT_BLANK_CHARACTERS = (
    "\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020"
    "\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)


def _trim_project_text(value: object) -> object:
    return value.strip(_PROJECT_TEXT_BLANK_CHARACTERS) if isinstance(value, str) else value


Code = Annotated[
    str, StringConstraints(min_length=1, max_length=40), BeforeValidator(_trim_project_text)
]
Name = Annotated[
    str, StringConstraints(min_length=1, max_length=160), BeforeValidator(_trim_project_text)
]
Reason = Annotated[
    str, StringConstraints(min_length=1, max_length=500), BeforeValidator(_trim_project_text)
]
Version = Annotated[int, Field(strict=True, ge=1)]
Journey = Literal["initial", "improve", "transition", "migrate", "audit", "expand"]
StepStatus = Literal["not_started", "in_progress", "blocked", "reported", "feature_pending"]
CATALOG_VERSION = "guided-qms-v1"


class _CatalogStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    position: int
    feature_pending: bool


class _CatalogJourney(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: Journey
    steps: tuple[_CatalogStep, ...]


class _Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["guided-qms-v1"]
    journeys: tuple[_CatalogJourney, ...]


CATALOG = _Catalog.model_validate_json(
    files("pmc_api").joinpath("qms_project_catalog.json").read_text()
)
CATALOG_STEPS = {journey.key: journey.steps for journey in CATALOG.journeys}


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    code: Code
    name: Name
    journey_key: Journey
    scope_summary: str = Field(default="", max_length=4000)
    coordinator_user_id: UUID | None = None
    target_date: date | None = None


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Version
    name: Name | None = None
    scope_summary: str | None = Field(default=None, max_length=4000)
    coordinator_user_id: UUID | None = None
    target_date: date | None = None

    @model_validator(mode="after")
    def changes(self) -> ProjectPatch:
        changed = self.model_fields_set - {"expected_version"}
        if not changed or any(
            getattr(self, k) is None for k in changed & {"name", "scope_summary"}
        ):
            raise ValueError("provide non-null project changes")
        return self


class StatusCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Version
    target_status: Literal["open", "archived"]
    reason: Reason


class StepPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_project_version: Version
    expected_version: Version
    status: StepStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    assignee_user_id: UUID | None = None
    target_date: date | None = None

    @model_validator(mode="after")
    def changes(self) -> StepPatch:
        changed = self.model_fields_set - {"expected_version", "expected_project_version"}
        if not changed or any(getattr(self, k) is None for k in changed & {"status", "notes"}):
            raise ValueError("provide non-null step changes")
        if (
            self.status in {"blocked", "reported"}
            and self.notes is not None
            and not self.notes.strip(_PROJECT_TEXT_BLANK_CHARACTERS)
        ):
            raise ValueError("blocked or reported work requires meaningful notes")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    code: str
    name: str
    journey_key: Journey
    catalog_version: str
    scope_summary: str
    coordinator_user_id: UUID | None
    target_date: date | None
    status: Literal["open", "archived"]
    row_version: Version
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    project_id: UUID
    step_key: str
    position: int
    status: StepStatus
    notes: str
    assignee_user_id: UUID | None
    target_date: date | None
    row_version: Version
    updated_by_user_id: UUID
    updated_at: datetime


class ProjectDetail(ProjectResponse):
    steps: list[StepResponse]


def _detail(db: Session, row: QMSProject) -> ProjectDetail:
    # One SQL statement gives readers a coherent parent/step snapshot even if
    # another transaction committed between the initial visibility check and here.
    records = list(
        db.execute(
            select(QMSProject, QMSProjectStep)
            .outerjoin(QMSProjectStep, QMSProjectStep.project_id == QMSProject.id)
            .where(QMSProject.id == row.id, QMSProject.tenant_id == row.tenant_id)
            .order_by(QMSProjectStep.position)
            .execution_options(populate_existing=True)
        )
    )
    if not records:
        raise HTTPException(404, "project not found")
    return ProjectDetail(
        **ProjectResponse.model_validate(records[0][0]).model_dump(),
        steps=[
            StepResponse.model_validate(record[1]) for record in records if record[1] is not None
        ],
    )


def _write_authority(db: Session, unit_id: UUID) -> None:
    require_capability(db, "projects.read", unit_id)
    require_capability(db, "projects.manage", unit_id)


def _database_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else getattr(original, "sqlstate", None)
    if state in {"23503", "23505", "23514", "40001", "40P01", "55P03"}:
        raise HTTPException(
            409, "project scope, assignment, catalog or version conflicts"
        ) from None
    if state == "42501":
        raise HTTPException(403, "project authority denied") from None
    raise error


def _project_values(row: QMSProject) -> dict[str, object]:
    return {
        "unit_id": str(row.unit_id),
        "code": row.code,
        "name_hash": hashlib.sha256(row.name.encode()).hexdigest(),
        "journey_key": row.journey_key,
        "catalog_version": row.catalog_version,
        "scope_summary_hash": hashlib.sha256(row.scope_summary.encode()).hexdigest(),
        "coordinator_user_id": str(row.coordinator_user_id) if row.coordinator_user_id else None,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "status": row.status,
        "row_version": row.row_version,
    }


def _step_values(row: QMSProjectStep, project: QMSProject) -> dict[str, object]:
    return {
        "unit_id": str(row.unit_id),
        "project_id": str(row.project_id),
        "project_row_version": project.row_version,
        "step_key": row.step_key,
        "position": row.position,
        "status": row.status,
        "row_version": row.row_version,
        "notes_hash": hashlib.sha256(row.notes.encode()).hexdigest(),
        "assignee_user_id": str(row.assignee_user_id) if row.assignee_user_id else None,
        "target_date": row.target_date.isoformat() if row.target_date else None,
    }


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    project: QMSProject,
    action: str,
    before: dict[str, object] | None,
    *,
    step: QMSProjectStep | None = None,
    reason: str | None = None,
) -> ProjectDetail:
    try:
        db.flush()
        after = _step_values(step, project) if step else _project_values(project)
        if reason is not None:
            after["reason_hash"] = hashlib.sha256(reason.encode()).hexdigest()
        audit_service.record_qms_project(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=step.id if step else project.id,
            request_id=request_id,
            old_values=before,
            new_values=after,
        )
        # Materialize response within the same authorized transaction; commit resets app.* context.
        result = _detail(db, project)
        db.commit()
        return result
    except DBAPIError as error:
        _database_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


def _locked(db: Session, actor: OrganizationActor, project_id: UUID, version: int) -> QMSProject:
    # SELECT FOR UPDATE also applies UPDATE RLS. Check readable scope first so
    # a read-only actor receives the explicit capability denial (403).
    query = select(QMSProject).where(
        QMSProject.id == project_id, QMSProject.tenant_id == actor.tenant_id
    )
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "project not found")
    _write_authority(db, row.unit_id)
    try:
        row = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    except DBAPIError as error:
        _database_error(db, error)
        raise AssertionError("unreachable") from error
    if row is None:
        raise HTTPException(404, "project not found")
    if row.row_version != version:
        raise HTTPException(409, "project changed; refresh before retrying")
    if row.catalog_version != CATALOG_VERSION:
        raise HTTPException(409, "project catalog is unsupported")
    return row


@router.get("", response_model=list[ProjectResponse])
def projects(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> list[QMSProject]:
    actor = actor_context(db, authenticated)
    require_capability(db, "projects.read", unit_id)
    return list(
        db.scalars(
            select(QMSProject)
            .where(QMSProject.tenant_id == actor.tenant_id, QMSProject.unit_id == unit_id)
            .order_by(QMSProject.code, QMSProject.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/{project_id}", response_model=ProjectDetail)
def project(project_id: UUID, db: DBSession, authenticated: Authenticated) -> ProjectDetail:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSProject).where(
            QMSProject.id == project_id, QMSProject.tenant_id == actor.tenant_id
        )
    )
    if row is None:
        raise HTTPException(404, "project not found")
    require_capability(db, "projects.read", row.unit_id)
    return _detail(db, row)


@router.post(
    "", response_model=ProjectDetail, status_code=201, dependencies=[Depends(require_csrf)]
)
def create(
    request: Request, body: ProjectInput, db: DBSession, authenticated: Authenticated
) -> ProjectDetail:
    actor = actor_context(db, authenticated)
    _write_authority(db, body.unit_id)
    now = datetime.now(UTC)
    row = QMSProject(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        catalog_version=CATALOG_VERSION,
        step_write_id=None,
        status="open",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
    except DBAPIError as error:
        _database_error(db, error)
    db.add_all(
        QMSProjectStep(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            unit_id=body.unit_id,
            project_id=row.id,
            step_key=s.key,
            position=s.position,
            status="feature_pending" if s.feature_pending else "not_started",
            notes="",
            assignee_user_id=None,
            target_date=None,
            row_version=1,
            source_project_version=1,
            updated_by_user_id=actor.user_id,
            updated_at=now,
        )
        for s in CATALOG_STEPS[body.journey_key]
    )
    return _finish(db, actor, request.state.request_id, row, "qms_project.created", None)


@router.patch("/{project_id}", response_model=ProjectDetail, dependencies=[Depends(require_csrf)])
def update(
    request: Request,
    project_id: UUID,
    body: ProjectPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> ProjectDetail:
    actor = actor_context(db, authenticated)
    row = _locked(db, actor, project_id, body.expected_version)
    if row.status != "open":
        raise HTTPException(409, "restore archived project before editing")
    before = _project_values(row)
    for key, value in body.model_dump(exclude_unset=True, exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.row_version += 1
    row.step_write_id = None
    row.updated_at = datetime.now(UTC)
    return _finish(db, actor, request.state.request_id, row, "qms_project.updated", before)


@router.post(
    "/{project_id}/status", response_model=ProjectDetail, dependencies=[Depends(require_csrf)]
)
def status(
    request: Request,
    project_id: UUID,
    body: StatusCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> ProjectDetail:
    actor = actor_context(db, authenticated)
    row = _locked(db, actor, project_id, body.expected_version)
    if row.status == body.target_status:
        raise HTTPException(409, "project status transition is invalid")
    before = _project_values(row)
    row.step_write_id = None
    row.status, row.row_version, row.updated_at = (
        body.target_status,
        row.row_version + 1,
        datetime.now(UTC),
    )
    return _finish(
        db,
        actor,
        request.state.request_id,
        row,
        "qms_project.archived" if row.status == "archived" else "qms_project.restored",
        before,
        reason=body.reason,
    )


@router.patch(
    "/{project_id}/steps/{step_id}",
    response_model=ProjectDetail,
    dependencies=[Depends(require_csrf)],
)
def update_step(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    body: StepPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> ProjectDetail:
    actor = actor_context(db, authenticated)
    row = _locked(db, actor, project_id, body.expected_project_version)
    if row.status != "open":
        raise HTTPException(409, "restore archived project before editing steps")
    step = db.scalar(
        select(QMSProjectStep)
        .where(QMSProjectStep.id == step_id, QMSProjectStep.project_id == row.id)
        .execution_options(populate_existing=True)
    )
    if step is None:
        raise HTTPException(404, "project step not found")
    if step.row_version != body.expected_version:
        raise HTTPException(409, "step changed; refresh before retrying")
    changes = body.model_dump(
        exclude_unset=True, exclude={"expected_version", "expected_project_version"}
    )
    target_status = changes.get("status", step.status)
    if (step.status == "feature_pending" and target_status != "feature_pending") or (
        step.status != "feature_pending" and target_status == "feature_pending"
    ):
        raise HTTPException(422, "product gap status is fixed by catalog")
    if target_status in {"blocked", "reported"} and not str(changes.get("notes", step.notes)).strip(
        _PROJECT_TEXT_BLANK_CHARACTERS
    ):
        raise HTTPException(422, "blocked or reported work requires meaningful notes")
    before = _step_values(step, row)
    row.row_version += 1
    row.step_write_id = step.id
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()  # Parent version advances before the guarded child update.
    except DBAPIError as error:
        _database_error(db, error)
    for key, value in changes.items():
        setattr(step, key, value)
    step.row_version += 1
    step.source_project_version = row.row_version
    step.updated_by_user_id = actor.user_id
    step.updated_at = row.updated_at
    return _finish(
        db, actor, request.state.request_id, row, "qms_project_step.updated", before, step=step
    )
