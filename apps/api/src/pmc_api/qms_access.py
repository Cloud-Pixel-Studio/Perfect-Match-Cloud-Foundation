"""Explicit, scoped business capabilities; commercial seats never grant authority."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import String, Uuid, and_, cast, column, func, or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db, set_request_context
from pmc_api.models import OrganizationUnit, QMSAccessGrant
from pmc_api.organization_service import OrganizationActor, require_context

CAPABILITIES = frozenset(
    {
        "documents.read",
        "documents.author",
        "documents.review",
        "documents.approve",
        "documents.release",
        "documents.obsolete",
        "evidence.read",
        "evidence.create",
        "evidence.review",
        "processes.read",
        "processes.manage",
        "controls.read",
        "controls.manage",
        "control_instances.read",
        "control_instances.manage",
        "risks.read",
        "risks.manage",
        "risks.review",
        "ncr.read",
        "ncr.manage",
        "ncr.review",
        "capa.read",
        "capa.manage",
        "capa.review",
        "audits.read",
        "audits.manage",
        "audits.execute",
        "audits.review",
    }
)
router = APIRouter(prefix="/qms-access", tags=["qms-access"])
DBSession = Annotated[Session, Depends(get_db)]


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    unit_id: UUID
    capability: str


class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    unit_id: UUID
    capability: str
    status: str
    granted_by_user_id: UUID
    created_at: datetime
    revoked_by_user_id: UUID | None
    revoked_at: datetime | None


class EffectiveAccessResponse(BaseModel):
    unit_id: UUID
    capabilities: list[str]


class ActiveCapabilitiesResponse(BaseModel):
    capabilities: list[str]


class GrantHistoryRead(GrantResponse):
    member_name: str | None
    unit_name: str | None
    unit_code: str | None
    unit_status: Literal["active", "archived"] | None


class GrantHistoryPage(BaseModel):
    tenant_id: UUID
    viewer_user_id: UUID
    viewer_role: str
    items: list[GrantHistoryRead]
    next_cursor: str | None


class _GrantCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    tenant_id: UUID
    viewer_user_id: UUID
    viewer_role: str = Field(pattern=r"^(owner|admin|member|auditor)$")
    filters_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: AwareDatetime
    grant_id: UUID


def _history_cursor(raw: str, actor: OrganizationActor, digest: str) -> _GrantCursor:
    # Encoded pagination state, not an authority token. RLS and the current
    # authenticated actor always decide which rows can be read.
    try:
        decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
        cursor = _GrantCursor.model_validate_json(decoded)
    except ValueError:
        raise HTTPException(400, "invalid permission history cursor") from None
    if (
        cursor.tenant_id != actor.tenant_id
        or cursor.viewer_user_id != actor.user_id
        or cursor.viewer_role != actor.role
        or cursor.filters_digest != digest
    ):
        raise HTTPException(409, "permission history context changed; refresh the list")
    return cursor


def actor_context(db: Session, authenticated: Authenticated) -> OrganizationActor:
    set_request_context(
        db,
        user_id=authenticated.user.id,
        tenant_id=authenticated.record.current_tenant_id,
    )
    actor = require_context(
        db, user_id=authenticated.user.id, tenant_id=authenticated.record.current_tenant_id
    )
    set_request_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    return actor


def require_capability(db: Session, capability: str, unit_id: UUID | None) -> None:
    if (
        capability not in CAPABILITIES
        or unit_id is None
        or not db.scalar(
            text("SELECT qms_has_capability(:capability, :unit)"),
            {"capability": capability, "unit": unit_id},
        )
    ):
        raise HTTPException(403, "QMS capability is not granted for this scope")


def active_capabilities(db: Session, actor: OrganizationActor) -> list[str]:
    rows = db.scalars(
        text(
            "SELECT DISTINCT g.capability FROM qms_access_grants g "
            "WHERE g.tenant_id=:tenant_id AND g.user_id=:user_id AND g.status='active' "
            "AND qms_has_capability(g.capability,g.unit_id) ORDER BY g.capability"
        ),
        {"tenant_id": actor.tenant_id, "user_id": actor.user_id},
    )
    return list(rows)


def _owner(actor: OrganizationActor) -> None:
    if actor.role != "owner":
        raise HTTPException(403, "only the tenant owner can manage QMS capability grants")


def _audit(db: Session, actor: OrganizationActor, row: QMSAccessGrant, request_id: UUID) -> None:
    audit_service.record_qms_access(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action="qms.access_granted" if row.status == "active" else "qms.access_revoked",
        resource_id=row.id,
        request_id=request_id,
        new_values={
            "user_id": str(row.user_id),
            "unit_id": str(row.unit_id),
            "capability": row.capability,
            "status": row.status,
        },
    )


def create_grant(
    db: Session, actor: OrganizationActor, request_id: UUID, body: GrantInput
) -> QMSAccessGrant:
    actor = require_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    _owner(actor)
    if body.user_id == actor.user_id:
        raise HTTPException(403, "self-granting QMS capabilities is not allowed")
    if body.capability not in CAPABILITIES:
        raise HTTPException(422, "unknown QMS capability")
    row = QMSAccessGrant(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        user_id=body.user_id,
        unit_id=body.unit_id,
        capability=body.capability,
        status="active",
        granted_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
    )
    try:
        db.add(row)
        db.flush()
        _audit(db, actor, row, request_id)
        db.commit()
    except DBAPIError as error:
        db.rollback()
        original = error.orig
        details = original.args[0] if original is not None and original.args else None
        sqlstate = details.get("C") if isinstance(details, dict) else None
        if sqlstate in {"23503", "23505", "23514"}:
            raise HTTPException(409, "grant target, scope or active grant is invalid") from None
        if sqlstate == "42501":
            raise HTTPException(403, "QMS grant authority denied") from None
        raise
    except Exception:
        db.rollback()
        raise
    return row


def revoke_grant(
    db: Session, actor: OrganizationActor, request_id: UUID, grant_id: UUID
) -> QMSAccessGrant:
    actor = require_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    _owner(actor)
    row = db.scalar(
        select(QMSAccessGrant)
        .where(QMSAccessGrant.id == grant_id, QMSAccessGrant.tenant_id == actor.tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "QMS access grant not found")
    if row.status != "active":
        raise HTTPException(409, "QMS access grant is already revoked")
    try:
        row.status = "revoked"
        row.revoked_by_user_id = actor.user_id
        row.revoked_at = datetime.now(UTC)
        db.flush()
        _audit(db, actor, row, request_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


@router.get("/grants", response_model=list[GrantResponse])
def grants(db: DBSession, authenticated: Authenticated, response: Response) -> list[QMSAccessGrant]:
    actor = actor_context(db, authenticated)
    response.headers["Cache-Control"] = "private, no-store"
    return list(
        db.scalars(
            select(QMSAccessGrant)
            .where(QMSAccessGrant.tenant_id == actor.tenant_id)
            .order_by(QMSAccessGrant.created_at.desc(), QMSAccessGrant.id)
            .limit(100)
        )
    )


@router.get("/grants/page", response_model=GrantHistoryPage)
def grant_history(
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=2048),
    grant_status: Literal["all", "active", "revoked"] = Query(default="all", alias="status"),
    q: str = Query(default="", max_length=160),
    user_id: UUID | None = None,
    unit_id: UUID | None = None,
    capability: str | None = Query(default=None, max_length=40),
) -> GrantHistoryPage:
    actor = actor_context(db, authenticated)
    if actor.role != "owner" and user_id is not None and user_id != actor.user_id:
        raise HTTPException(403, "permission history is restricted to your own grants")
    if capability is not None and capability not in CAPABILITIES:
        raise HTTPException(422, "unknown QMS capability")
    search = q.strip()
    filters = {
        "limit": limit,
        "status": grant_status,
        "q": search,
        "user_id": str(user_id) if user_id else None,
        "unit_id": str(unit_id) if unit_id else None,
        "capability": capability,
    }
    digest = hashlib.sha256(
        json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    after = _history_cursor(cursor, actor, digest) if cursor is not None else None
    directory = (
        func.organization_member_directory()
        .table_valued(column("user_id", Uuid), column("display_name", String))
        .alias("grant_directory")
    )
    statement = (
        select(
            QMSAccessGrant,
            directory.c.display_name,
            OrganizationUnit.name,
            OrganizationUnit.code,
            OrganizationUnit.status,
        )
        .select_from(QMSAccessGrant)
        .outerjoin(directory, directory.c.user_id == QMSAccessGrant.user_id)
        .outerjoin(
            OrganizationUnit,
            and_(
                OrganizationUnit.id == QMSAccessGrant.unit_id,
                OrganizationUnit.tenant_id == QMSAccessGrant.tenant_id,
            ),
        )
        .where(QMSAccessGrant.tenant_id == actor.tenant_id)
    )
    # The explicit bound complements RLS; non-owners never gain a tenant-wide
    # directory or history by changing a filter, cursor or browser role.
    if actor.role != "owner":
        statement = statement.where(QMSAccessGrant.user_id == actor.user_id)
    if user_id is not None:
        statement = statement.where(QMSAccessGrant.user_id == user_id)
    if unit_id is not None:
        statement = statement.where(QMSAccessGrant.unit_id == unit_id)
    if capability is not None:
        statement = statement.where(QMSAccessGrant.capability == capability)
    if grant_status != "all":
        statement = statement.where(QMSAccessGrant.status == grant_status)
    if search:
        literal_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{literal_search}%"
        statement = statement.where(
            or_(
                directory.c.display_name.ilike(pattern, escape="\\"),
                OrganizationUnit.name.ilike(pattern, escape="\\"),
                OrganizationUnit.code.ilike(pattern, escape="\\"),
                QMSAccessGrant.capability.ilike(pattern, escape="\\"),
                cast(QMSAccessGrant.id, String).ilike(pattern, escape="\\"),
                cast(QMSAccessGrant.user_id, String).ilike(pattern, escape="\\"),
            )
        )
    if after is not None:
        statement = statement.where(
            or_(
                QMSAccessGrant.created_at < after.created_at,
                and_(
                    QMSAccessGrant.created_at == after.created_at,
                    QMSAccessGrant.id > after.grant_id,
                ),
            )
        )
    rows = list(
        db.execute(
            statement.order_by(QMSAccessGrant.created_at.desc(), QMSAccessGrant.id).limit(limit + 1)
        )
    )
    current = require_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    if current.role != actor.role:
        raise HTTPException(403, "permission history access changed; refresh your identity")
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        GrantHistoryRead(
            **GrantResponse.model_validate(row[0]).model_dump(),
            member_name=row[1],
            unit_name=row[2],
            unit_code=row[3],
            unit_status=row[4],
        )
        for row in rows
    ]
    next_cursor = None
    if has_more:
        last = rows[-1][0]
        value = _GrantCursor(
            tenant_id=actor.tenant_id,
            viewer_user_id=actor.user_id,
            viewer_role=actor.role,
            filters_digest=digest,
            created_at=last.created_at,
            grant_id=last.id,
        )
        next_cursor = (
            base64.urlsafe_b64encode(value.model_dump_json().encode()).decode().rstrip("=")
        )
    response.headers["Cache-Control"] = "private, no-store"
    return GrantHistoryPage(
        tenant_id=actor.tenant_id,
        viewer_user_id=actor.user_id,
        viewer_role=actor.role,
        items=items,
        next_cursor=next_cursor,
    )


@router.get("/effective", response_model=EffectiveAccessResponse)
def effective_access(
    db: DBSession, authenticated: Authenticated, unit_id: UUID
) -> EffectiveAccessResponse:
    actor_context(db, authenticated)
    active = [
        capability
        for capability in sorted(CAPABILITIES)
        if db.scalar(
            text("SELECT qms_has_capability(:capability, :unit)"),
            {"capability": capability, "unit": unit_id},
        )
    ]
    return EffectiveAccessResponse(unit_id=unit_id, capabilities=active)


@router.get("/active-capabilities", response_model=ActiveCapabilitiesResponse)
def active_capability_summary(
    db: DBSession, authenticated: Authenticated
) -> ActiveCapabilitiesResponse:
    actor = actor_context(db, authenticated)
    return ActiveCapabilitiesResponse(capabilities=active_capabilities(db, actor))


@router.post(
    "/grants", response_model=GrantResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
def grant(
    request: Request, body: GrantInput, db: DBSession, authenticated: Authenticated
) -> QMSAccessGrant:
    return create_grant(db, actor_context(db, authenticated), request.state.request_id, body)


@router.post(
    "/grants/{grant_id}/revoke", response_model=GrantResponse, dependencies=[Depends(require_csrf)]
)
def revoke(
    request: Request, grant_id: UUID, db: DBSession, authenticated: Authenticated
) -> QMSAccessGrant:
    return revoke_grant(db, actor_context(db, authenticated), request.state.request_id, grant_id)
