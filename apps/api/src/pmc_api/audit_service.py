from __future__ import annotations

import json
import re
from collections.abc import Callable
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
WORKFLOW_ACTIONS = {
    "workflow.definition_created": "workflow_definition",
    "workflow.definition_updated": "workflow_definition",
    "workflow.definition_retired": "workflow_definition",
    "workflow.version_created": "workflow_version",
    "workflow.version_updated": "workflow_version",
    "workflow.version_published": "workflow_version",
    "workflow.step_created": "workflow_step",
    "workflow.step_updated": "workflow_step",
    "workflow.transition_created": "workflow_transition",
    "workflow.transition_updated": "workflow_transition",
    "workflow.assignment_created": "workflow_assignment",
    "workflow.assignment_updated": "workflow_assignment",
    "workflow.instance_started": "workflow_instance",
    "workflow.instance_transitioned": "workflow_instance",
    "workflow.instance_completed": "workflow_instance",
    "workflow.instance_cancelled": "workflow_instance",
}
WORKFLOW_ACTION_FIELDS = {
    "workflow.definition_created": frozenset({"workflow_definition_id", "status"}),
    "workflow.definition_updated": frozenset({"workflow_definition_id", "status"}),
    "workflow.definition_retired": frozenset({"workflow_definition_id", "status"}),
    "workflow.version_created": frozenset(
        {"workflow_version_id", "workflow_definition_id", "version_number", "status"}
    ),
    "workflow.version_updated": frozenset(
        {"workflow_version_id", "workflow_definition_id", "version_number", "status"}
    ),
    "workflow.version_published": frozenset(
        {"workflow_version_id", "workflow_definition_id", "version_number", "status"}
    ),
    "workflow.step_created": frozenset(
        {"step_id", "workflow_version_id", "step_key", "name", "step_type", "is_start", "position"}
    ),
    "workflow.step_updated": frozenset(
        {"step_id", "workflow_version_id", "step_key", "name", "step_type", "is_start", "position"}
    ),
    "workflow.transition_created": frozenset(
        {
            "transition_id",
            "workflow_version_id",
            "from_step_id",
            "to_step_id",
            "transition_key",
            "label",
        }
    ),
    "workflow.transition_updated": frozenset(
        {
            "transition_id",
            "workflow_version_id",
            "from_step_id",
            "to_step_id",
            "transition_key",
            "label",
        }
    ),
    "workflow.assignment_created": frozenset(
        {
            "assignment_id",
            "workflow_version_id",
            "step_id",
            "target_type",
            "target_user_id",
            "target_organization_unit_id",
            "target_application_role",
        }
    ),
    "workflow.assignment_updated": frozenset(
        {
            "assignment_id",
            "workflow_version_id",
            "step_id",
            "target_type",
            "target_user_id",
            "target_organization_unit_id",
            "target_application_role",
        }
    ),
    "workflow.instance_started": frozenset(
        {"workflow_instance_id", "workflow_version_id", "to_step_id", "status", "row_version"}
    ),
    "workflow.instance_transitioned": frozenset(
        {
            "workflow_instance_id",
            "workflow_version_id",
            "from_step_id",
            "to_step_id",
            "transition_id",
            "status",
            "row_version",
        }
    ),
    "workflow.instance_completed": frozenset(
        {"workflow_instance_id", "workflow_version_id", "to_step_id", "status", "row_version"}
    ),
    "workflow.instance_cancelled": frozenset(
        {"workflow_instance_id", "workflow_version_id", "to_step_id", "status", "row_version"}
    ),
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
    expected_resource = {**ORGANIZATION_ACTIONS, **WORKFLOW_ACTIONS}.get(action)
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


def _record_workflow(
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
    allowed = WORKFLOW_ACTION_FIELDS.get(action)
    if allowed is None:
        raise AuditPayloadError("unsupported workflow audit action")
    for payload in (old_values, new_values):
        if payload is not None and not set(payload).issubset(allowed):
            raise AuditPayloadError("workflow audit payload contains an unsupported field")
    return _record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_display_name=actor_display_name,
        actor_role=actor_role,
        action=action,
        resource_type=WORKFLOW_ACTIONS[action],
        resource_id=resource_id,
        request_id=request_id,
        old_values=old_values,
        new_values=new_values,
        metadata={"source": "workflow_service"},
    )


def _workflow_builder(action: str) -> Callable[..., AuditEvent]:
    def record(db: Session, **kwargs: object) -> AuditEvent:
        return _record_workflow(db, action=action, **kwargs)  # type: ignore[arg-type]

    return record


record_workflow_definition_created = _workflow_builder("workflow.definition_created")
record_workflow_definition_updated = _workflow_builder("workflow.definition_updated")
record_workflow_definition_retired = _workflow_builder("workflow.definition_retired")
record_workflow_version_created = _workflow_builder("workflow.version_created")
record_workflow_version_updated = _workflow_builder("workflow.version_updated")
record_workflow_version_published = _workflow_builder("workflow.version_published")
record_workflow_step_created = _workflow_builder("workflow.step_created")
record_workflow_step_updated = _workflow_builder("workflow.step_updated")
record_workflow_transition_created = _workflow_builder("workflow.transition_created")
record_workflow_transition_updated = _workflow_builder("workflow.transition_updated")
record_workflow_assignment_created = _workflow_builder("workflow.assignment_created")
record_workflow_assignment_updated = _workflow_builder("workflow.assignment_updated")
record_workflow_instance_started = _workflow_builder("workflow.instance_started")
record_workflow_instance_transitioned = _workflow_builder("workflow.instance_transitioned")
record_workflow_instance_completed = _workflow_builder("workflow.instance_completed")
record_workflow_instance_cancelled = _workflow_builder("workflow.instance_cancelled")
