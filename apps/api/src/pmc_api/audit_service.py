from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from pmc_api.models import AuditEvent

AUDIT_SCHEMA_VERSION = 1
PROCESS_ACTIONS = {
    action: "qms_process"
    for action in (
        "process.created",
        "process.updated",
        "process.archived",
        "process.restored",
    )
}
CONTROL_ACTIONS = {
    **{
        action: "qms_control"
        for action in ("control.created", "control.updated", "control.activated", "control.retired")
    },
    **{
        action: "qms_control_instance"
        for action in (
            "control_instance.created",
            "control_instance.updated",
            "control_instance.transitioned",
        )
    },
    **{
        action: "qms_control_activity"
        for action in (
            "control.activity_created",
            "control.activity_updated",
            "control.activity_deactivated",
        )
    },
    **{
        action: "qms_control_evidence_requirement"
        for action in (
            "control.evidence_requirement_created",
            "control.evidence_requirement_updated",
            "control.evidence_requirement_deactivated",
        )
    },
    **{
        action: "qms_control_instance_activity"
        for action in (
            "control_instance_activity.created",
            "control_instance_activity.updated",
            "control_instance_activity.transitioned",
        )
    },
    **{
        action: "qms_control_instance_evidence"
        for action in (
            "control_instance_evidence.created",
            "control_instance_evidence.updated",
            "control_instance_evidence.submitted",
            "control_instance_evidence.accepted",
            "control_instance_evidence.rejected",
        )
    },
}
QMS_ACCESS_ACTIONS = {
    "qms.access_granted": "qms_access_grant",
    "qms.access_revoked": "qms_access_grant",
}
ACTION_TENANT_SELECTED = "auth.tenant_selected"
RISK_ACTIONS = {
    action: "qms_risk"
    for action in ("risk.created", "risk.updated", "risk.transitioned", "risk.reviewed")
}
NCR_ACTIONS = {
    action: "qms_nonconformity" for action in ("ncr.created", "ncr.updated", "ncr.transitioned")
}
CAPA_ACTIONS = {
    action: "qms_capa"
    for action in (
        "capa.created",
        "capa.updated",
        "capa.analysis_started",
        "capa.analysis_updated",
        "capa.plan_started",
        "capa.implementation_started",
        "capa.effectiveness_review_started",
        "capa.effectiveness_decided",
        "capa.closed",
        "capa.cancelled",
    )
}
CAPA_ITEM_ACTIONS = {
    action: "qms_capa_action"
    for action in ("capa.action_created", "capa.action_updated", "capa.action_transitioned")
}
CAPA_EFFECTIVENESS_ACTIONS = {"capa.effectiveness_recorded": "qms_capa_effectiveness_review"}
CAPA_EFFECTIVENESS_AUDIT_FIELDS = frozenset(
    {
        "capa_id",
        "unit_id",
        "cycle_number",
        "decision",
        "notes_hash",
        "reviewer_user_id",
        "reviewed_at",
        "implementation_started_by_user_id",
        "implementation_started_at",
        "review_started_by_user_id",
        "review_started_at",
        "active_action_count",
        "verified_action_count",
        "cancelled_action_count",
    }
)
CAPA_ITEM_AUDIT_FIELDS = frozenset(
    {
        "capa_id",
        "unit_id",
        "title_hash",
        "description_hash",
        "owner_user_id",
        "due_date",
        "state",
        "completed_by_user_id",
        "completed_at",
        "verified_by_user_id",
        "verified_at",
        "verification_notes_hash",
        "cancelled_by_user_id",
        "cancelled_at",
        "cancellation_reason_hash",
        "row_version",
        "created_by_user_id",
        "created_at",
        "updated_at",
    }
)
CAPA_AUDIT_FIELDS = frozenset(
    {
        "unit_id",
        "process_id",
        "code",
        "name",
        "source_type",
        "source_ncr_id",
        "source_risk_id",
        "source_code",
        "source_state",
        "source_reference_hash",
        "owner_user_id",
        "target_date",
        "root_cause_method",
        "state",
        "row_version",
        "problem_statement_hash",
        "analysis_data_hash",
        "analysis_summary_hash",
        "verified_root_cause_hash",
        "other_method_name_hash",
        "analysis_started_by_user_id",
        "analysis_started_at",
        "plan_summary_hash",
        "planned_by_user_id",
        "planned_at",
        "implementation_started_by_user_id",
        "implementation_started_at",
        "review_started_by_user_id",
        "review_started_at",
        "effective_by_user_id",
        "effective_at",
        "closed_by_user_id",
        "closed_at",
        "closure_notes_hash",
        "cancelled_by_user_id",
        "cancelled_at",
        "cancellation_reason_hash",
    }
)
NCR_AUDIT_FIELDS = frozenset(
    {
        "unit_id",
        "process_id",
        "code",
        "name",
        "source_type",
        "severity",
        "detected_date",
        "detected_by_user_id",
        "owner_user_id",
        "containment_required",
        "containment_owner_user_id",
        "containment_date",
        "containment_completed",
        "disposition",
        "target_date",
        "state",
        "opened_by_user_id",
        "opened_at",
        "reviewed_by_user_id",
        "reviewed_at",
        "closed_by_user_id",
        "closed_at",
        "cancelled_by_user_id",
        "cancelled_at",
        "row_version",
        "description_hash",
        "containment_action_hash",
        "disposition_notes_hash",
        "root_cause_summary_hash",
        "closure_notes_hash",
        "cancellation_reason_hash",
    }
)
RISK_LINK_ACTIONS = {
    action: "qms_risk_link"
    for action in (
        "risk.control_linked",
        "risk.control_unlinked",
        "risk.document_linked",
        "risk.document_unlinked",
    )
}
RISK_LINK_COMMON_FIELDS = frozenset(
    {
        "risk_id",
        "unit_id",
        "risk_row_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
        "removal_reason_hash",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "linked_target_version",
    }
)
NCR_LINK_ACTIONS = {
    action: "qms_ncr_link"
    for action in (
        "ncr.risk_linked",
        "ncr.risk_unlinked",
        "ncr.control_linked",
        "ncr.control_unlinked",
        "ncr.evidence_linked",
        "ncr.evidence_unlinked",
        "ncr.document_linked",
        "ncr.document_unlinked",
    )
}
NCR_LINK_COMMON_FIELDS = frozenset(
    {
        "nonconformity_id",
        "unit_id",
        "ncr_row_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
        "removal_reason_hash",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "linked_target_version",
    }
)
CAPA_DOCUMENT_LINK_ACTIONS = {
    action: "qms_capa_document_link"
    for action in ("capa.document_linked", "capa.document_unlinked")
}
CAPA_DOCUMENT_LINK_AUDIT_FIELDS = frozenset(
    {
        "capa_id",
        "unit_id",
        "capa_row_version",
        "document_id",
        "document_revision_id",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "snapshot_revision",
        "file_sha256",
        "linked_target_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
        "removal_reason_hash",
    }
)
CAPA_TRACE_LINK_ACTIONS = {
    action: "qms_capa_trace_link"
    for action in (
        "capa.control_linked",
        "capa.control_unlinked",
        "capa.evidence_linked",
        "capa.evidence_unlinked",
    )
}
CAPA_TRACE_LINK_COMMON_FIELDS = frozenset(
    {
        "capa_id",
        "unit_id",
        "capa_row_version",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "linked_target_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
        "removal_reason_hash",
    }
)
RISK_AUDIT_FIELDS = frozenset(
    {
        "unit_id",
        "process_id",
        "code",
        "name",
        "risk_type",
        "category",
        "source_hash",
        "description_hash",
        "cause_hash",
        "potential_effect_hash",
        "benefit_hash",
        "opportunity_action_hash",
        "mitigation_plan_hash",
        "closure_notes_hash",
        "owner_user_id",
        "likelihood",
        "impact",
        "residual_likelihood",
        "residual_impact",
        "response_strategy",
        "target_date",
        "review_date",
        "state",
        "scoring_model",
        "threshold_moderate",
        "threshold_high",
        "threshold_critical",
        "assessed_by_user_id",
        "assessed_at",
        "reviewed_by_user_id",
        "reviewed_at",
        "closed_by_user_id",
        "closed_at",
        "row_version",
    }
)
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
    expected_resource = {
        **ORGANIZATION_ACTIONS,
        **WORKFLOW_ACTIONS,
        **QMS_ACCESS_ACTIONS,
        **PROCESS_ACTIONS,
        **CONTROL_ACTIONS,
        **RISK_ACTIONS,
        **NCR_ACTIONS,
        **CAPA_ACTIONS,
        **CAPA_ITEM_ACTIONS,
        **CAPA_EFFECTIVENESS_ACTIONS,
        **NCR_LINK_ACTIONS,
        **CAPA_DOCUMENT_LINK_ACTIONS,
        **CAPA_TRACE_LINK_ACTIONS,
        **RISK_LINK_ACTIONS,
        **{name: definition[0] for name, definition in DOCUMENT_ACTIONS.items()},
    }.get(action)
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


def record_qms_access(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in QMS_ACCESS_ACTIONS:
        raise AuditPayloadError("unsupported QMS access audit action")
    payload = kwargs.get("new_values")
    allowed = {"user_id", "unit_id", "capability", "status"}
    if not isinstance(payload, dict) or set(payload) != allowed:
        raise AuditPayloadError("QMS access audit payload fields are invalid")
    return _record(db, resource_type="qms_access_grant", **kwargs)  # type: ignore[arg-type]


def record_process(db: Session, **kwargs: object) -> AuditEvent:
    if kwargs.get("action") not in PROCESS_ACTIONS:
        raise AuditPayloadError("unsupported process audit action")
    allowed = {
        "unit_id",
        "code",
        "name",
        "process_type",
        "parent_id",
        "owner_user_id",
        "sequence",
        "department",
        "status",
        "row_version",
        "description_hash",
        "inputs_hash",
        "outputs_hash",
        "site_ids",
    }
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (not isinstance(payload, dict) or set(payload) != allowed):
            raise AuditPayloadError("process audit payload fields are invalid")
    return _record(db, resource_type="qms_process", **kwargs)  # type: ignore[arg-type]


def record_ncr(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in NCR_ACTIONS:
        raise AuditPayloadError("unsupported nonconformity audit action")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        expected = NCR_AUDIT_FIELDS | (
            {"decision"} if field == "new_values" and action == "ncr.transitioned" else set()
        )
        if payload is not None and (not isinstance(payload, dict) or set(payload) != expected):
            raise AuditPayloadError("nonconformity audit payload fields are invalid")
    return _record(db, resource_type="qms_nonconformity", **kwargs)  # type: ignore[arg-type]


def record_capa(db: Session, **kwargs: object) -> AuditEvent:
    if kwargs.get("action") not in CAPA_ACTIONS:
        raise AuditPayloadError("unsupported CAPA audit action")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (
            not isinstance(payload, dict) or set(payload) != CAPA_AUDIT_FIELDS
        ):
            raise AuditPayloadError("CAPA audit payload fields are invalid")
    return _record(db, resource_type="qms_capa", **kwargs)  # type: ignore[arg-type]


def record_capa_action(db: Session, **kwargs: object) -> AuditEvent:
    if kwargs.get("action") not in CAPA_ITEM_ACTIONS:
        raise AuditPayloadError("unsupported CAPA action audit event")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (
            not isinstance(payload, dict) or set(payload) != CAPA_ITEM_AUDIT_FIELDS
        ):
            raise AuditPayloadError("CAPA action audit payload fields are invalid")
    return _record(db, resource_type="qms_capa_action", **kwargs)  # type: ignore[arg-type]


def record_capa_effectiveness_review(db: Session, **kwargs: object) -> AuditEvent:
    if kwargs.get("action") not in CAPA_EFFECTIVENESS_ACTIONS:
        raise AuditPayloadError("unsupported CAPA effectiveness audit event")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (
            not isinstance(payload, dict) or set(payload) != CAPA_EFFECTIVENESS_AUDIT_FIELDS
        ):
            raise AuditPayloadError("CAPA effectiveness audit payload fields are invalid")
    return _record(db, resource_type="qms_capa_effectiveness_review", **kwargs)  # type: ignore[arg-type]


def record_risk(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in RISK_ACTIONS:
        raise AuditPayloadError("unsupported risk audit action")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        expected = RISK_AUDIT_FIELDS
        if field == "new_values" and action in {"risk.transitioned", "risk.reviewed"}:
            expected = expected | {"decision"}
        if payload is not None and (not isinstance(payload, dict) or set(payload) != expected):
            raise AuditPayloadError("risk audit payload fields are invalid")
    return _record(db, resource_type="qms_risk", **kwargs)  # type: ignore[arg-type]


def record_risk_link(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in RISK_LINK_ACTIONS:
        raise AuditPayloadError("unsupported risk link audit action")
    allowed = RISK_LINK_COMMON_FIELDS | (
        {"control_instance_id"}
        if action.startswith("risk.control_")
        else {"document_id", "document_revision_id", "snapshot_revision", "file_sha256"}
    )
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (not isinstance(payload, dict) or set(payload) != allowed):
            raise AuditPayloadError("risk link audit payload fields are invalid")
    return _record(db, resource_type="qms_risk_link", **kwargs)  # type: ignore[arg-type]


def record_ncr_link(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in NCR_LINK_ACTIONS:
        raise AuditPayloadError("unsupported NCR link audit action")
    allowed = NCR_LINK_COMMON_FIELDS | (
        {"risk_id"}
        if action.startswith("ncr.risk_")
        else (
            {"control_instance_id"}
            if action.startswith("ncr.control_")
            else (
                {"evidence_id", "control_instance_id"}
                if action.startswith("ncr.evidence_")
                else {"document_id", "document_revision_id", "snapshot_revision", "file_sha256"}
            )
        )
    )
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (not isinstance(payload, dict) or set(payload) != allowed):
            raise AuditPayloadError("NCR link audit payload fields are invalid")
    return _record(db, resource_type="qms_ncr_link", **kwargs)  # type: ignore[arg-type]


def record_capa_document_link(db: Session, **kwargs: object) -> AuditEvent:
    if kwargs.get("action") not in CAPA_DOCUMENT_LINK_ACTIONS:
        raise AuditPayloadError("unsupported CAPA document link action")
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (
            not isinstance(payload, dict) or set(payload) != CAPA_DOCUMENT_LINK_AUDIT_FIELDS
        ):
            raise AuditPayloadError("CAPA document link audit fields are invalid")
    return _record(db, resource_type="qms_capa_document_link", **kwargs)  # type: ignore[arg-type]


def record_capa_trace_link(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in CAPA_TRACE_LINK_ACTIONS:
        raise AuditPayloadError("unsupported CAPA trace link action")
    allowed = CAPA_TRACE_LINK_COMMON_FIELDS | (
        {"control_instance_id"}
        if action.startswith("capa.control_")
        else {"evidence_id", "control_instance_id"}
    )
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        if payload is not None and (not isinstance(payload, dict) or set(payload) != allowed):
            raise AuditPayloadError("CAPA trace link audit fields are invalid")
    return _record(db, resource_type="qms_capa_trace_link", **kwargs)  # type: ignore[arg-type]


def record_control(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    if action not in CONTROL_ACTIONS:
        raise AuditPayloadError("unsupported control audit action")
    resource_type = CONTROL_ACTIONS[action]
    allowed = (
        {
            "unit_id",
            "process_id",
            "code",
            "name",
            "objective_hash",
            "description_hash",
            "category",
            "guidance_hashes",
            "owner_user_id",
            "state",
            "row_version",
        }
        if resource_type == "qms_control"
        else {
            "unit_id",
            "process_id",
            "control_id",
            "control_instance_id",
            "requirement_definition_id",
            "sequence",
            "name",
            "description_hash",
            "acceptance_criteria_hash",
            "evidence_type",
            "mandatory",
            "document_id",
            "document_revision_id",
            "evidence_summary_hash",
            "status",
            "submitted_by_user_id",
            "submitted_at",
            "reviewed_by_user_id",
            "reviewed_at",
            "review_decision_hash",
            "row_version",
        }
        if resource_type == "qms_control_instance_evidence"
        else {
            "unit_id",
            "process_id",
            "control_id",
            "control_instance_id",
            "activity_definition_id",
            "sequence",
            "name",
            "description_hash",
            "objective_hash",
            "why_it_matters_hash",
            "implementation_steps_hash",
            "success_criteria_hash",
            "activity_kind",
            "readiness_required",
            "responsible_role",
            "expected_output_hash",
            "evidence_expectations_hash",
            "assigned_to_user_id",
            "status",
            "target_date",
            "completion_summary_hash",
            "notes_hash",
            "completed_by_user_id",
            "completed_at",
            "row_version",
        }
        if resource_type == "qms_control_instance_activity"
        else {
            "unit_id",
            "process_id",
            "control_id",
            "code",
            "name",
            "owner_user_id",
            "implementation_status",
            "applicability",
            "justification_hash",
            "target_date",
            "implementation_date",
            "review_date",
            "notes_hash",
            "status",
            "row_version",
        }
        if resource_type == "qms_control_instance"
        else {
            "unit_id",
            "process_id",
            "control_id",
            "sequence",
            "name",
            "description_hash",
            "objective_hash",
            "why_it_matters_hash",
            "implementation_steps_hash",
            "success_criteria_hash",
            "activity_kind",
            "readiness_required",
            "responsible_role",
            "expected_output_hash",
            "evidence_expectations_hash",
            "definition_key",
            "active",
            "row_version",
        }
        if resource_type == "qms_control_activity"
        else {
            "unit_id",
            "process_id",
            "control_id",
            "sequence",
            "name",
            "description_hash",
            "acceptance_criteria_hash",
            "evidence_type",
            "mandatory",
            "definition_key",
            "active",
            "row_version",
        }
    )
    for field in ("old_values", "new_values"):
        payload = kwargs.get(field)
        expected = allowed
        if field == "new_values" and action == "control_instance.transitioned":
            expected = allowed | {"decision"}
        if field == "new_values" and action == "control_instance_activity.transitioned":
            expected = allowed | {"decision"}
        if payload is not None and (not isinstance(payload, dict) or set(payload) != expected):
            raise AuditPayloadError("control audit payload fields are invalid")
    return _record(db, resource_type=resource_type, **kwargs)  # type: ignore[arg-type]


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

DOCUMENT_REVISION_AUDIT_FIELDS = frozenset(
    {
        "document_id",
        "revision",
        "status",
        "prepared_by_user_id",
        "reviewed_by_user_id",
        "approved_by_user_id",
        "file_state",
        "row_version",
        "file_sha256",
        "file_size",
        "effective_date",
        "review_date",
    }
)

DOCUMENT_ACTIONS = {
    "document.created": (
        "qms_document",
        frozenset(
            {
                "unit_id",
                "process_id",
                "code",
                "title",
                "document_type",
                "owner_user_id",
                "status",
                "current_revision_id",
                "row_version",
            }
        ),
    ),
    "document.obsoleted": (
        "qms_document",
        frozenset(
            {
                "unit_id",
                "process_id",
                "code",
                "title",
                "document_type",
                "owner_user_id",
                "status",
                "current_revision_id",
                "row_version",
            }
        ),
    ),
    "revision.created": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
    "revision.updated": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
    "revision.submitted": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
    "revision.rejected": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
    "revision.approved": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
    "revision.released": ("qms_document_revision", DOCUMENT_REVISION_AUDIT_FIELDS),
}


def record_document(db: Session, **kwargs: object) -> AuditEvent:
    action = str(kwargs.get("action", ""))
    definition = DOCUMENT_ACTIONS.get(action)
    if definition is None:
        raise AuditPayloadError("unsupported document audit action")
    resource_type, fields = definition
    for key in ("old_values", "new_values"):
        value = kwargs.get(key)
        if value is not None and (not isinstance(value, dict) or set(value) != fields):
            raise AuditPayloadError("document audit fields are invalid")
    return _record(db, resource_type=resource_type, **kwargs)  # type: ignore[arg-type]
