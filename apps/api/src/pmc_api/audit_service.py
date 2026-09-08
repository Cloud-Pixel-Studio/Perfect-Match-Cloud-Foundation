from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from pmc_api.models import AuditEvent

AUDIT_SCHEMA_VERSION = 1
ACTION_TENANT_SELECTED = "auth.tenant_selected"
ORGANIZATION_ACTIONS = {
    "organization.unit_created": "organization_unit",
    "organization.unit_updated": "organization_unit",
    "organization.unit_moved": "organization_unit",
    "organization.unit_archived": "organization_unit",
    "organization.unit_restored": "organization_unit",
    "organization.assignment_created": "organization_assignment",
    "organization.assignment_updated": "organization_assignment",
    "organization.assignment_deactivated": "organization_assignment",
    "organization.assignment_reactivated": "organization_assignment",
}
ORGANIZATION_UNIT_FIELDS = frozenset(
    {"unit_id", "code", "name", "unit_type", "parent_id", "status"}
)
ORGANIZATION_ASSIGNMENT_FIELDS = frozenset(
    {"assignment_id", "unit_id", "user_id", "assignment_role", "is_primary", "status"}
)
MAX_PAYLOAD_BYTES = 64 * 1024
FORBIDDEN_KEYS = {
    "password",
    "userpassword",
    "sessiontoken",
    "csrftoken",
    "authorizationcode",
    "pkceverifier",
    "loginbinding",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "cookie",
    "cookievalue",
    "apikey",
    "privatekey",
    "clientsecret",
    "databasepassword",
    "awscredential",
    "githubcredential",
}


class AuditPayloadError(ValueError):
    pass


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def validate_payload(value: object, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normalize_key(str(key))
            if normalized in FORBIDDEN_KEYS:
                raise AuditPayloadError(f"forbidden audit field: {path}.{key}")
            validate_payload(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_payload(nested, f"{path}[{index}]")


def _safe(value: dict[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    validate_payload(value)
    if (
        len(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode())
        > MAX_PAYLOAD_BYTES
    ):
        raise AuditPayloadError("audit payload exceeds maximum size")
    return value


def _record(
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
    expected_resource = ORGANIZATION_ACTIONS.get(action)
    if action != ACTION_TENANT_SELECTED and expected_resource != resource_type:
        raise AuditPayloadError("audit action or resource type is invalid")
    if not resource_type or len(resource_type) > 80:
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
        changed_fields=sorted(
            key for key in {*before, *after} if before.get(key) != after.get(key)
        ),
        old_values=old_values,
        new_values=new_values,
        event_metadata=metadata,
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    return event


def record_tenant_selected(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    actor_display_name: str,
    actor_role: str,
    resource_id: UUID,
    request_id: UUID,
) -> AuditEvent:
    """Append the fixed, minimal payload for a validated tenant selection."""
    return _record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_display_name=actor_display_name,
        actor_role=actor_role,
        action=ACTION_TENANT_SELECTED,
        resource_type="application_session",
        resource_id=resource_id,
        request_id=request_id,
        old_values=None,
        new_values={"selected": True},
        metadata={"selection": "validated"},
    )


def _record_organization(
    db: Session,
    *,
    action: str,
    tenant_id: UUID,
    actor_user_id: UUID,
    actor_display_name: str,
    actor_role: str,
    resource_id: UUID,
    request_id: UUID,
    old_values: dict[str, object] | None = None,
    new_values: dict[str, object] | None = None,
) -> AuditEvent:
    allowed = (
        ORGANIZATION_UNIT_FIELDS
        if ORGANIZATION_ACTIONS[action] == "organization_unit"
        else ORGANIZATION_ASSIGNMENT_FIELDS
    )
    for payload in (old_values, new_values):
        if payload is not None and not set(payload).issubset(allowed):
            raise AuditPayloadError("organization audit payload contains an unsupported field")
    return _record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_display_name=actor_display_name,
        actor_role=actor_role,
        action=action,
        resource_type=ORGANIZATION_ACTIONS[action],
        resource_id=resource_id,
        request_id=request_id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "organization_service"},
    )


def record_organization_unit_created(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.unit_created", **kwargs)  # type: ignore[arg-type]


def record_organization_unit_updated(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.unit_updated", **kwargs)  # type: ignore[arg-type]


def record_organization_unit_moved(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.unit_moved", **kwargs)  # type: ignore[arg-type]


def record_organization_unit_archived(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.unit_archived", **kwargs)  # type: ignore[arg-type]


def record_organization_unit_restored(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.unit_restored", **kwargs)  # type: ignore[arg-type]


def record_organization_assignment_created(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.assignment_created", **kwargs)  # type: ignore[arg-type]


def record_organization_assignment_updated(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.assignment_updated", **kwargs)  # type: ignore[arg-type]


def record_organization_assignment_deactivated(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.assignment_deactivated", **kwargs)  # type: ignore[arg-type]


def record_organization_assignment_reactivated(db: Session, **kwargs: object) -> AuditEvent:
    return _record_organization(db, action="organization.assignment_reactivated", **kwargs)  # type: ignore[arg-type]
