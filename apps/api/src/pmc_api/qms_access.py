"""Explicit, scoped business capabilities; commercial seats never grant authority."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db, set_request_context
from pmc_api.models import QMSAccessGrant
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
def grants(db: DBSession, authenticated: Authenticated) -> list[QMSAccessGrant]:
    actor = actor_context(db, authenticated)
    return list(
        db.scalars(
            select(QMSAccessGrant)
            .where(QMSAccessGrant.tenant_id == actor.tenant_id)
            .order_by(QMSAccessGrant.created_at.desc(), QMSAccessGrant.id)
            .limit(100)
        )
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
