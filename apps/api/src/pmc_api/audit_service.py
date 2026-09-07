from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from pmc_api.models import AuditEvent

AUDIT_SCHEMA_VERSION = 1
ACTION_TENANT_SELECTED = "auth.tenant_selected"
MAX_PAYLOAD_BYTES = 64 * 1024
FORBIDDEN_KEYS = {
    "password",
    "session_token",
    "csrf_token",
    "authorization_code",
    "pkce_verifier",
    "login_binding",
    "access_token",
    "refresh_token",
    "id_token",
    "cookie",
    "api_key",
    "private_key",
    "client_secret",
    "database_password",
    "aws_credential",
    "github_credential",
}


class AuditPayloadError(ValueError):
    pass


def _validate(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if normalized in FORBIDDEN_KEYS or any(
                part in normalized for part in ("token", "secret")
            ):
                raise AuditPayloadError(f"forbidden audit field: {key}")
            _validate(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate(nested)


def _safe(value: dict[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    _validate(value)
    if (
        len(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode())
        > MAX_PAYLOAD_BYTES
    ):
        raise AuditPayloadError("audit payload exceeds maximum size")
    return value


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
    old_values, new_values = _safe(old_values), _safe(new_values)
    metadata = _safe(metadata or {}) or {}
    before, after = old_values or {}, new_values or {}
    event = AuditEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_display_name=actor_display_name,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        schema_version=AUDIT_SCHEMA_VERSION,
        changed_fields=sorted(key for key in {*before, *after} if before.get(key) != after.get(key)),
        old_values=old_values, new_values=new_values, metadata=metadata,
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    return event
