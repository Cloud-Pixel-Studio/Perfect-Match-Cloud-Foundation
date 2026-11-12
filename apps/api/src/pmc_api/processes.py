"""Tenant- and unit-scoped QMS process register."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import OrganizationUnit, QMSProcess, QMSProcessSite
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/processes", tags=["processes"])
DBSession = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Kind = Annotated[str, StringConstraints(pattern="^(management|core|support|other)$")]
Content = Annotated[str, StringConstraints(max_length=4000)]


class ProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    code: Code
    name: Name
    process_type: Kind = "core"
    parent_id: UUID | None = None
    owner_user_id: UUID | None = None
    sequence: int = Field(default=10, ge=0, le=10000)
    department: str = Field(default="", max_length=160)
    description: Content = ""
    inputs: Content = ""
    outputs: Content = ""
    site_ids: list[UUID] = Field(default_factory=list, max_length=100)


class ProcessPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    code: Code | None = None
    name: Name | None = None
    process_type: Kind | None = None
    parent_id: UUID | None = None
    owner_user_id: UUID | None = None
    sequence: int | None = Field(default=None, ge=0, le=10000)
    department: str | None = Field(default=None, max_length=160)
    description: Content | None = None
    inputs: Content | None = None
    outputs: Content | None = None
    site_ids: list[UUID] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_changes(self) -> ProcessPatch:
        changed = self.model_fields_set - {"expected_version"}
        if "site_ids" in changed and self.site_ids is None:
            raise ValueError("site_ids must be a list")
        if not changed or any(
            getattr(self, field) is None
            for field in changed - {"parent_id", "owner_user_id", "site_ids"}
        ):
            raise ValueError("provide non-null process changes")
        return self


class VersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class ProcessResponse(ProcessInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    row_version: int
    created_at: datetime
    updated_at: datetime


def _response(db: Session, row: QMSProcess) -> ProcessResponse:
    result = ProcessResponse.model_validate(row)
    sites = db.scalars(
        select(QMSProcessSite.site_unit_id)
        .where(QMSProcessSite.process_id == row.id)
        .order_by(QMSProcessSite.site_unit_id)
    )
    return result.model_copy(update={"site_ids": list(sites)})


class ScopeResponse(BaseModel):
    id: UUID
    name: str
    code: str
    can_manage: bool


def _values(db: Session, row: QMSProcess) -> dict[str, object]:
    return {
        "unit_id": str(row.unit_id),
        "code": row.code,
        "name": row.name,
        "process_type": row.process_type,
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
        "sequence": row.sequence,
        "department": row.department,
        "status": row.status,
        "row_version": row.row_version,
        **{
            f"{field}_hash": hashlib.sha256(getattr(row, field).encode()).hexdigest()
            for field in ("description", "inputs", "outputs")
        },
        "site_ids": sorted(
            str(site_id)
            for site_id in db.scalars(
                select(QMSProcessSite.site_unit_id).where(QMSProcessSite.process_id == row.id)
            )
        ),
    }


def _database_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(
            409, "process hierarchy, site, owner, scope or version conflicts"
        ) from None
    if state == "42501":
        raise HTTPException(403, "process authority denied") from None
    raise error


def _commit(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSProcess,
    action: str,
    before: dict[str, object] | None,
) -> QMSProcess:
    try:
        db.flush()
        audit_service.record_process(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(db, row),
        )
        db.commit()
    except DBAPIError as error:
        _database_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def create_process(
    db: Session, actor: OrganizationActor, request_id: UUID, body: ProcessInput
) -> QMSProcess:
    require_capability(db, "processes.manage", body.unit_id)
    now = datetime.now(UTC)
    site_ids = body.site_ids
    row = QMSProcess(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(exclude={"site_ids"}),
        status="active",
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
    _replace_sites(db, row, site_ids)
    return _commit(db, actor, request_id, row, "process.created", None)


def _replace_sites(db: Session, process: QMSProcess, site_ids: list[UUID]) -> None:
    if len(site_ids) != len(set(site_ids)):
        raise HTTPException(422, "site_ids must not contain duplicates")
    db.execute(delete(QMSProcessSite).where(QMSProcessSite.process_id == process.id))
    db.add_all(
        QMSProcessSite(
            tenant_id=process.tenant_id,
            process_id=process.id,
            process_unit_id=process.unit_id,
            site_unit_id=site_id,
            created_at=datetime.now(UTC),
        )
        for site_id in site_ids
    )


def _locked(
    db: Session, actor: OrganizationActor, process_id: UUID, expected_version: int
) -> QMSProcess:
    row = db.scalar(
        select(QMSProcess)
        .where(QMSProcess.id == process_id, QMSProcess.tenant_id == actor.tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "process not found")
    require_capability(db, "processes.manage", row.unit_id)
    if row.row_version != expected_version:
        raise HTTPException(409, "process changed; refresh before retrying")
    return row


def update_process(
    db: Session, actor: OrganizationActor, request_id: UUID, process_id: UUID, body: ProcessPatch
) -> QMSProcess:
    row = _locked(db, actor, process_id, body.expected_version)
    if row.status != "active":
        raise HTTPException(409, "restore an archived process before editing")
    before = _values(db, row)
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    site_ids = changes.pop("site_ids", None)
    for key, value in changes.items():
        setattr(row, key, value)
    if site_ids is not None:
        _replace_sites(db, row, site_ids)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _commit(db, actor, request_id, row, "process.updated", before)


def change_status(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    process_id: UUID,
    body: VersionCommand,
    new_status: str,
) -> QMSProcess:
    row = _locked(db, actor, process_id, body.expected_version)
    if new_status not in {"active", "archived"} or row.status == new_status:
        raise HTTPException(409, "process status transition is invalid")
    before = _values(db, row)
    row.status = new_status
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _commit(
        db,
        actor,
        request_id,
        row,
        "process.restored" if new_status == "active" else "process.archived",
        before,
    )


@router.get("/scopes", response_model=list[ScopeResponse])
def scopes(db: DBSession, authenticated: Authenticated) -> list[ScopeResponse]:
    actor = actor_context(db, authenticated)
    rows = db.execute(
        select(
            OrganizationUnit.id,
            OrganizationUnit.name,
            OrganizationUnit.code,
            func.qms_has_capability("processes.manage", OrganizationUnit.id),
        )
        .where(
            OrganizationUnit.tenant_id == actor.tenant_id,
            OrganizationUnit.status == "active",
            func.qms_has_capability("processes.read", OrganizationUnit.id)
            | func.qms_has_capability("processes.manage", OrganizationUnit.id),
        )
        .order_by(OrganizationUnit.name, OrganizationUnit.id)
        .limit(100)
    )
    return [ScopeResponse(id=row[0], name=row[1], code=row[2], can_manage=row[3]) for row in rows]


def list_processes(
    db: Session,
    actor: OrganizationActor,
    unit_id: UUID | None,
    limit: int,
    offset: int,
    search: str = "",
) -> list[QMSProcess]:
    query = select(QMSProcess).where(QMSProcess.tenant_id == actor.tenant_id)
    if unit_id is not None:
        query = query.where(QMSProcess.unit_id == unit_id)
    if search.strip():
        pattern = (
            "%" + search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        )
        query = query.where(
            QMSProcess.code.ilike(pattern, escape="!") | QMSProcess.name.ilike(pattern, escape="!")
        )
    return list(
        db.scalars(
            query.order_by(QMSProcess.sequence, QMSProcess.code, QMSProcess.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("", response_model=list[ProcessResponse])
def processes(
    db: DBSession,
    authenticated: Authenticated,
    unit_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    search: Annotated[str, Query(max_length=160)] = "",
) -> list[ProcessResponse]:
    return [
        _response(db, row)
        for row in list_processes(
            db, actor_context(db, authenticated), unit_id, limit, offset, search
        )
    ]


@router.get("/{process_id}", response_model=ProcessResponse)
def process(process_id: UUID, db: DBSession, authenticated: Authenticated) -> ProcessResponse:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSProcess).where(
            QMSProcess.id == process_id, QMSProcess.tenant_id == actor.tenant_id
        )
    )
    if row is None:
        raise HTTPException(404, "process not found")
    return _response(db, row)


@router.post(
    "", response_model=ProcessResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
def create(
    request: Request, body: ProcessInput, db: DBSession, authenticated: Authenticated
) -> ProcessResponse:
    row = create_process(db, actor_context(db, authenticated), request.state.request_id, body)
    return _response(db, row)


@router.patch("/{process_id}", response_model=ProcessResponse, dependencies=[Depends(require_csrf)])
def update(
    request: Request,
    process_id: UUID,
    body: ProcessPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> ProcessResponse:
    row = update_process(
        db, actor_context(db, authenticated), request.state.request_id, process_id, body
    )
    return _response(db, row)


@router.post(
    "/{process_id}/archive", response_model=ProcessResponse, dependencies=[Depends(require_csrf)]
)
def archive(
    request: Request,
    process_id: UUID,
    body: VersionCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> ProcessResponse:
    row = change_status(
        db, actor_context(db, authenticated), request.state.request_id, process_id, body, "archived"
    )
    return _response(db, row)


@router.post(
    "/{process_id}/restore", response_model=ProcessResponse, dependencies=[Depends(require_csrf)]
)
def restore(
    request: Request,
    process_id: UUID,
    body: VersionCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> ProcessResponse:
    row = change_status(
        db, actor_context(db, authenticated), request.state.request_id, process_id, body, "active"
    )
    return _response(db, row)
