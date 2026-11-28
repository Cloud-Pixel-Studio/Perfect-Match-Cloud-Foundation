"""Active company context for business operations, independent from authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pmc_api.database import set_request_context
from pmc_api.models import ApplicationSession, Membership, Tenant, User

if TYPE_CHECKING:
    from pmc_api.auth import AuthenticatedSession


@dataclass(frozen=True)
class TenantAccess:
    user_id: UUID
    display_name: str
    role: str
    tenant_id: UUID


def require_tenant_access(db: Session, *, user_id: UUID, tenant_id: UUID | None) -> TenantAccess:
    """Read current status in one statement; never authorize from cached ORM state.

    Callers establish the authenticated user context before this lookup. Keeping
    this outside require_session lets a suspended company's member still sign
    out, list authorized companies, or select another active company.
    """
    if tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tenant selection required")
    row = db.execute(
        select(Membership.role, User.display_name)
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
            User.status == "active",
            Tenant.status == "active",
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant access denied")
    role, display_name = row
    return TenantAccess(user_id, display_name, role, tenant_id)


def require_selected_tenant_access(
    db: Session, authenticated: AuthenticatedSession, tenant_id: UUID
) -> TenantAccess:
    """Bind a company-specific request to the session until the transaction ends."""
    user_id = authenticated.user.id
    set_request_context(db, user_id=user_id, session_hash=authenticated.record.token_hash)
    current = db.scalar(
        select(ApplicationSession)
        .where(
            ApplicationSession.id == authenticated.record.id, ApplicationSession.user_id == user_id
        )
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if current is None or current.revoked_at or current.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired or invalid")
    if current.current_tenant_id != tenant_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "company selection changed")
    actor = require_tenant_access(db, user_id=user_id, tenant_id=tenant_id)
    set_request_context(db, user_id=user_id, tenant_id=tenant_id)
    return actor
