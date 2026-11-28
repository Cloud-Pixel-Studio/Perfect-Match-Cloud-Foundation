from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from pmc_api.audit_service import record_employee
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.employee_portraits import receive_portrait
from pmc_api.models import EmployeeProfile, OrganizationUnit
from pmc_api.tenant_access import TenantAccess, require_selected_tenant_access

router = APIRouter(prefix="/employees/{tenant_id}", tags=["employees"])
DBSession = Annotated[Session, Depends(get_db)]
ProfileText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
ExpectedVersion = Annotated[int, Query(ge=1, le=2147483647)]


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: UUID
    full_name: ProfileText
    job_title: ProfileText

    @field_validator("full_name", "job_title")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
            raise ValueError("use single-line text")
        return value


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(strict=True, ge=1, le=2147483647)


class ProfileUpdate(ProfileInput, VersionInput):
    pass


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    unit_id: UUID
    full_name: str
    job_title: str
    status: str
    row_version: int
    has_portrait: bool
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class DirectoryPage(BaseModel):
    items: list[ProfileResponse]
    has_more: bool


def _context(db: Session, auth: Authenticated, tenant_id: UUID, response: Response) -> TenantAccess:
    actor = require_selected_tenant_access(db, auth, tenant_id)
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "employee administration requires owner or admin")
    response.headers["X-Tenant-ID"] = str(tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    return actor


def _profile_for_update(
    db: Session, actor: TenantAccess, profile_id: UUID, version: int
) -> EmployeeProfile:
    row = db.scalar(
        select(EmployeeProfile)
        .where(EmployeeProfile.tenant_id == actor.tenant_id, EmployeeProfile.id == profile_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "employee profile not found")
    if row.row_version != version or row.row_version == 2147483647:
        raise HTTPException(409, "employee profile changed; reload the directory")
    return row


def _active_unit(db: Session, actor: TenantAccess, unit_id: UUID) -> None:
    if (
        db.scalar(
            select(OrganizationUnit.id).where(
                OrganizationUnit.id == unit_id,
                OrganizationUnit.tenant_id == actor.tenant_id,
                OrganizationUnit.status == "active",
            )
        )
        is None
    ):
        raise HTTPException(409, "select an active organization unit")


def _audit_values(row: EmployeeProfile) -> dict[str, object]:
    return {"unit_id": str(row.unit_id), "status": row.status, "row_version": row.row_version}


def _save(
    db: Session,
    actor: TenantAccess,
    row: EmployeeProfile,
    request: Request,
    *,
    action: str,
    fields: list[str],
    previous: dict[str, object] | None = None,
) -> ProfileResponse:
    try:
        db.flush()
        record_employee(
            db,
            action=f"employee.{action}",
            fields=fields,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            resource_id=row.id,
            request_id=request.state.request_id,
            old_values=previous,
            new_values=_audit_values(row),
        )
        result = ProfileResponse.model_validate(row)
        db.commit()
        return result
    except DBAPIError as exc:
        db.rollback()
        args = getattr(exc.orig, "args", ())
        detail = args[0] if args and isinstance(args[0], dict) else {}
        code = getattr(exc.orig, "sqlstate", None) or detail.get("C")
        if code in {"23503", "23514"}:
            raise HTTPException(409, "employee profile or organization unit changed") from exc
        if code == "42501":
            raise HTTPException(403, "employee access changed") from exc
        if code == "P0064":
            raise HTTPException(507, "portrait exceeds the remaining company storage") from exc
        raise


@router.get("")
def list_profiles(
    tenant_id: UUID,
    response: Response,
    db: DBSession,
    auth: Authenticated,
    search: Annotated[str, Query(max_length=120)] = "",
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> DirectoryPage:
    actor = _context(db, auth, tenant_id, response)
    stmt = select(EmployeeProfile).where(EmployeeProfile.tenant_id == actor.tenant_id)
    if not include_archived:
        stmt = stmt.where(EmployeeProfile.status == "active")
    if term := search.strip():
        stmt = stmt.where(
            or_(
                EmployeeProfile.full_name.icontains(term, autoescape=True),
                EmployeeProfile.job_title.icontains(term, autoescape=True),
            )
        )
    rows = db.scalars(
        stmt.order_by(func.lower(EmployeeProfile.full_name), EmployeeProfile.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return DirectoryPage(
        items=[ProfileResponse.model_validate(row) for row in rows[:limit]],
        has_more=len(rows) > limit,
    )


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_profile(
    tenant_id: UUID,
    body: ProfileInput,
    request: Request,
    response: Response,
    db: DBSession,
    auth: Authenticated,
) -> ProfileResponse:
    actor = _context(db, auth, tenant_id, response)
    _active_unit(db, actor, body.unit_id)
    now = datetime.now(UTC)
    row = EmployeeProfile(
        id=uuid4(),
        tenant_id=tenant_id,
        unit_id=body.unit_id,
        full_name=body.full_name,
        job_title=body.job_title,
        status="active",
        row_version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    return _save(
        db,
        actor,
        row,
        request,
        action="created",
        fields=["full_name", "job_title", "unit_id", "status"],
    )


@router.patch("/{profile_id}", dependencies=[Depends(require_csrf)])
def update_profile(
    tenant_id: UUID,
    profile_id: UUID,
    body: ProfileUpdate,
    request: Request,
    response: Response,
    db: DBSession,
    auth: Authenticated,
) -> ProfileResponse:
    actor = _context(db, auth, tenant_id, response)
    row = _profile_for_update(db, actor, profile_id, body.expected_version)
    if row.status != "active":
        raise HTTPException(409, "restore the employee before editing")
    _active_unit(db, actor, body.unit_id)
    previous = _audit_values(row)
    values = {"full_name": body.full_name, "job_title": body.job_title, "unit_id": body.unit_id}
    changes = [key for key, value in values.items() if getattr(row, key) != value]
    if not changes:
        return ProfileResponse.model_validate(row)
    row.full_name, row.job_title, row.unit_id = body.full_name, body.job_title, body.unit_id
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, actor, row, request, action="updated", fields=changes, previous=previous)


@router.post("/{profile_id}/{command}", dependencies=[Depends(require_csrf)])
def change_status(
    tenant_id: UUID,
    profile_id: UUID,
    command: str,
    body: VersionInput,
    request: Request,
    response: Response,
    db: DBSession,
    auth: Authenticated,
) -> ProfileResponse:
    actor = _context(db, auth, tenant_id, response)
    if command not in {"archive", "restore"}:
        raise HTTPException(404, "employee command not found")
    row = _profile_for_update(db, actor, profile_id, body.expected_version)
    target = "active" if command == "restore" else "archived"
    if row.status == target:
        raise HTTPException(409, "employee profile already has that status")
    if target == "active":
        _active_unit(db, actor, row.unit_id)
    previous = _audit_values(row)
    row.status = target
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    action = "restored" if command == "restore" else "archived"
    return _save(db, actor, row, request, action=action, fields=["status"], previous=previous)


@router.get("/{profile_id}/photo", response_class=Response)
def get_portrait(
    tenant_id: UUID, profile_id: UUID, response: Response, db: DBSession, auth: Authenticated
) -> Response:
    actor = _context(db, auth, tenant_id, response)
    payload = db.scalar(
        select(EmployeeProfile.portrait).where(
            EmployeeProfile.tenant_id == actor.tenant_id, EmployeeProfile.id == profile_id
        )
    )
    if payload is None:
        raise HTTPException(404, "employee portrait not found")
    return Response(
        content=payload,
        media_type="image/jpeg",
        headers={
            **dict(response.headers),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


def _change_portrait(
    db: Session,
    actor: TenantAccess,
    profile_id: UUID,
    expected_version: int,
    request: Request,
    portrait: bytes | None,
) -> ProfileResponse:
    row = _profile_for_update(db, actor, profile_id, expected_version)
    if row.status != "active":
        raise HTTPException(409, "restore the employee before changing the photo")
    if row.portrait == portrait:
        return ProfileResponse.model_validate(row)
    previous = _audit_values(row)
    row.portrait = portrait
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    return _save(db, actor, row, request, action="updated", fields=["portrait"], previous=previous)


@router.put("/{profile_id}/photo", dependencies=[Depends(require_csrf)])
async def put_portrait(
    tenant_id: UUID,
    profile_id: UUID,
    expected_version: ExpectedVersion,
    request: Request,
    response: Response,
    db: DBSession,
    auth: Authenticated,
) -> ProfileResponse:
    actor = await run_in_threadpool(_context, db, auth, tenant_id, response)
    portrait = await receive_portrait(request)
    return await run_in_threadpool(
        _change_portrait, db, actor, profile_id, expected_version, request, portrait
    )


@router.delete("/{profile_id}/photo", dependencies=[Depends(require_csrf)])
def delete_portrait(
    tenant_id: UUID,
    profile_id: UUID,
    expected_version: ExpectedVersion,
    request: Request,
    response: Response,
    db: DBSession,
    auth: Authenticated,
) -> ProfileResponse:
    actor = _context(db, auth, tenant_id, response)
    return _change_portrait(db, actor, profile_id, expected_version, request, None)
