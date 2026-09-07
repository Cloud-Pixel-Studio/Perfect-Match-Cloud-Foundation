from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated
from pmc_api.database import get_db, set_request_context
from pmc_api.models import Membership, Tenant

router = APIRouter(prefix="/tenant", tags=["tenant"])
DBSession = Annotated[Session, Depends(get_db)]


class TenantContextResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


@router.get("/context", response_model=TenantContextResponse)
def tenant_context(db: DBSession, authenticated: Authenticated) -> TenantContextResponse:
    tenant_id = authenticated.record.current_tenant_id
    if tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tenant selection required")
    set_request_context(db, user_id=authenticated.user.id, tenant_id=tenant_id)
    row = db.execute(
        select(Tenant, Membership.role)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(
            Tenant.id == tenant_id,
            Membership.user_id == authenticated.user.id,
            Membership.status == "active",
        )
    ).one_or_none()
    if row is None:
        authenticated.record.current_tenant_id = None
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant access revoked")
    tenant, role = row
    return TenantContextResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, role=role)
