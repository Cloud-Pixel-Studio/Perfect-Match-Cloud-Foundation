from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated
from pmc_api.database import get_db, set_request_context
from pmc_api.models import AuditEvent, Membership


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID
    actor_display_name: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: UUID | None
    request_id: UUID
    schema_version: int
    changed_fields: list[str]
    old_values: dict[str, object] | None
    new_values: dict[str, object] | None
    metadata: dict[str, object] = Field(
        validation_alias="event_metadata", serialization_alias="metadata"
    )


class AuditEventPage(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None


def _cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if not value:
        return None
    try:
        raw_time, raw_id = value.split("|", 1)
        return datetime.fromisoformat(raw_time), UUID(raw_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid audit cursor") from exc


router = APIRouter(prefix="/audit", tags=["audit"])
DBSession = Annotated[Session, Depends(get_db)]


@router.get("/events", response_model=AuditEventPage)
def events(
    request: Request,
    response: Response,
    db: DBSession,
    authenticated: Authenticated,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    action: str | None = Query(default=None, max_length=120),
    resource_type: str | None = Query(default=None, max_length=80),
) -> AuditEventPage:
    tenant_id = authenticated.record.current_tenant_id
    if tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tenant selection required")
    set_request_context(
        db,
        user_id=authenticated.user.id,
        tenant_id=tenant_id,
        session_hash=authenticated.record.token_hash,
    )
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == authenticated.user.id,
            Membership.status == "active",
        )
    )
    if membership is None or membership.role not in {"owner", "admin", "auditor"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "audit access denied")
    statement = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if resource_type:
        statement = statement.where(AuditEvent.resource_type == resource_type)
    position = _cursor(cursor)
    if position:
        statement = statement.where(
            or_(
                AuditEvent.occurred_at < position[0],
                and_(
                    AuditEvent.occurred_at == position[0],
                    AuditEvent.id < position[1],
                ),
            )
        )
    rows = list(
        db.scalars(
            statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = f"{rows[-1].occurred_at.isoformat()}|{rows[-1].id}" if has_more and rows else None
    response.headers["X-Request-ID"] = str(request.state.request_id)
    return AuditEventPage(
        items=[AuditEventResponse.model_validate(row) for row in rows], next_cursor=next_cursor
    )
