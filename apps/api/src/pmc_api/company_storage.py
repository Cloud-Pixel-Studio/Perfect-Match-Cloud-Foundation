from __future__ import annotations

from typing import Annotated, Literal
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
UsageStatus = Literal["unconfigured", "normal", "notice", "warning", "at_limit", "over_limit"]


class StorageUsage(BaseModel):
    tenant_id: UUID
    recorded_bytes: int
    document_file_count: int
    employee_photo_bytes: int
    employee_photo_count: int
    allowance_bytes: int | None
    available_bytes: int | None
    usage_percent: int | None
    usage_status: UsageStatus


def _capacity_status(
    used: int, allowance: int | None
) -> tuple[int | None, int | None, UsageStatus]:
    if allowance is None:
        return None, None, "unconfigured"
    percent = min(100, used * 100 // allowance)
    if used > allowance:
        return 0, percent, "over_limit"
    if used == allowance:
        return 0, percent, "at_limit"
    if percent >= 90:
        return allowance - used, percent, "warning"
    if percent >= 80:
        return allowance - used, percent, "notice"
    return allowance - used, percent, "normal"


@router.get("/{tenant_id}")
def get_storage_usage(
    tenant_id: UUID, response: Response, db: DBSession, auth: Authenticated
) -> StorageUsage:
    actor = require_selected_tenant_access(db, auth, tenant_id)
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "company storage requires owner or admin")
    usage = db.execute(
        text(
            """
            SELECT
                COALESCE((SELECT recorded_bytes FROM public.company_document_storage
                          WHERE tenant_id = :tenant_id), 0) AS recorded_bytes,
                COALESCE((SELECT file_count FROM public.company_document_storage
                          WHERE tenant_id = :tenant_id), 0) AS file_count,
                COALESCE((SELECT employee_photo_bytes FROM public.company_document_storage
                          WHERE tenant_id = :tenant_id), 0) AS employee_photo_bytes,
                COALESCE((SELECT employee_photo_count FROM public.company_document_storage
                          WHERE tenant_id = :tenant_id), 0) AS employee_photo_count,
                (SELECT allowance_bytes FROM public.company_storage_allowances
                 WHERE tenant_id = :tenant_id ORDER BY row_version DESC LIMIT 1) AS allowance_bytes
            """
        ),
        {"tenant_id": actor.tenant_id},
    ).one()
    recorded_bytes = usage.recorded_bytes + usage.employee_photo_bytes
    available, percent, status = _capacity_status(recorded_bytes, usage.allowance_bytes)
    response.headers["X-Tenant-ID"] = str(actor.tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    return StorageUsage(
        tenant_id=actor.tenant_id,
        recorded_bytes=recorded_bytes,
        document_file_count=usage.file_count,
        employee_photo_bytes=usage.employee_photo_bytes,
        employee_photo_count=usage.employee_photo_count,
        allowance_bytes=usage.allowance_bytes,
        available_bytes=available,
        usage_percent=percent,
        usage_status=status,
    )
