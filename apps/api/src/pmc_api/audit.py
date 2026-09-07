from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from pmc_api.auth import Authenticated
from pmc_api.database import get_db, set_request_context
from pmc_api.models import AuditEvent, Membership

AUDIT_SCHEMA_VERSION = 1
ACTION_TENANT_SELECTED = "auth.tenant_selected"
MAX_PAYLOAD_BYTES = 64 * 1024
FORBIDDEN_KEYS = {
    "password", "session_token", "csrf_token", "authorization_code", "pkce_verifier",
    "login_binding", "access_token", "refresh_token", "id_token", "cookie", "api_key",
    "private_key", "client_secret", "database_password", "aws_credential", "github_credential",
}


class AuditPayloadError(ValueError):
    pass


def _validate_value(value: object, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if normalized in FORBIDDEN_KEYS or any(part in normalized for part in ("token", "secret")):
                raise AuditPayloadError(f"forbidden audit field: {path}.{key}")
            _validate_value(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_value(nested, f"{path}[{index}]")


def _safe_payload(value: dict[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    _validate_value(value)
    if len(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()) > MAX_PAYLOAD_BYTES:
        raise AuditPayloadError("audit payload exceeds maximum size")
    return value


def _changed_fields(old: dict[str, object] | None, new: dict[str, object] | None) -> list[str]:
    before, after = old or {}, new or {}
    return sorted(key for key in {*before, *after} if before.get(key) != after.get(key))


def record(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    actor_display_name: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    request_id: UUID,
    old_values: dict[str, object] | None = None,
    new_values: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    if action != ACTION_TENANT_SELECTED or not resource_type or len(resource_type) > 80:
        raise AuditPayloadError("audit action or resource type is invalid")
    old_values, new_values = _safe_payload(old_values), _safe_payload(new_values)
    metadata = _safe_payload(metadata or {}) or {}
    event = AuditEvent(
        id=uuid4(), tenant_id=tenant_id, actor_user_id=actor_user_id,
        actor_display_name=actor_display_name, actor_role=actor_role, action=action,
        resource_type=resource_type, resource_id=resource_id, request_id=request_id,
        schema_version=AUDIT_SCHEMA_VERSION, changed_fields=_changed_fields(old_values, new_values),
        old_values=old_values, new_values=new_values, metadata=metadata,
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    return event


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
    metadata: dict[str, object]


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
    set_request_context(db, user_id=authenticated.user.id, tenant_id=tenant_id, session_hash=authenticated.record.token_hash)
    membership = db.scalar(select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == authenticated.user.id, Membership.status == "active"))
    if membership is None or membership.role not in {"owner", "admin", "auditor"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "audit access denied")
    statement = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if resource_type:
        statement = statement.where(AuditEvent.resource_type == resource_type)
    position = _cursor(cursor)
    if position:
        statement = statement.where(tuple_(AuditEvent.occurred_at, AuditEvent.id) < tuple_(*position))
    rows = list(db.scalars(statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = f"{rows[-1].occurred_at.isoformat()}|{rows[-1].id}" if has_more and rows else None
    response.headers["X-Request-ID"] = str(request.state.request_id)
    return AuditEventPage(items=[AuditEventResponse.model_validate(row) for row in rows], next_cursor=next_cursor)
