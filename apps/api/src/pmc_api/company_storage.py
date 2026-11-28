from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated
from pmc_api.database import get_db
from pmc_api.tenant_access import require_selected_tenant_access

router = APIRouter(prefix="/company-storage", tags=["company-storage"])
DBSession = Annotated[Session, Depends(get_db)]


class StorageUsage(BaseModel):
    tenant_id: UUID
    recorded_bytes: int
    document_file_count: int


@router.get("/{tenant_id}")
def get_storage_usage(
    tenant_id: UUID, response: Response, db: DBSession, auth: Authenticated
) -> StorageUsage:
    actor = require_selected_tenant_access(db, auth, tenant_id)
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "company storage requires owner or admin")
    usage = db.execute(
        text(
            "SELECT recorded_bytes, file_count FROM public.company_document_storage "
            "WHERE tenant_id = :tenant_id"
        ),
        {"tenant_id": actor.tenant_id},
    ).one_or_none()
    response.headers["X-Tenant-ID"] = str(actor.tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    return StorageUsage(
        tenant_id=actor.tenant_id,
        recorded_bytes=usage.recorded_bytes if usage else 0,
        document_file_count=usage.file_count if usage else 0,
    )
