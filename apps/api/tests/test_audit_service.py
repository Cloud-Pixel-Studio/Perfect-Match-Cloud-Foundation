from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from pmc_api.audit_service import (
    DOCUMENT_ACTIONS,
    DOCUMENT_REVISION_AUDIT_FIELDS,
    NCR_AUDIT_FIELDS,
    NCR_LINK_ACTIONS,
    NCR_LINK_COMMON_FIELDS,
    RISK_ACTIONS,
    RISK_AUDIT_FIELDS,
    AuditPayloadError,
    record_ncr,
    record_ncr_link,
    record_risk,
    record_tenant_selected,
    validate_payload,
)


def test_audit_service_rejects_secret_key_variants() -> None:
    variants = [
        "password",
        "user_password",
        "userPassword",
        "session_token",
        "sessionToken",
        "csrf_token",
        "authorization_code",
        "pkce_verifier",
        "login_binding",
        "access_token",
        "refresh_token",
        "id_token",
        "cookie",
        "cookie_value",
        "api_key",
        "apiKey",
        "private_key",
        "privateKey",
        "client_secret",
        "clientSecret",
        "database_password",
        "aws_credential",
        "github_credential",
        "githubCredential",
    ]
    for key in variants:
        with pytest.raises(AuditPayloadError):
            validate_payload({"nested-list": [{key: "synthetic"}]})


def test_tenant_selection_uses_fixed_contract() -> None:
    record_tenant_selected(
        Session(),
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        actor_display_name="A",
        actor_role="owner",
        resource_id=uuid4(),
        request_id=uuid4(),
    )


def test_document_revision_transitions_have_fixed_audit_contracts() -> None:
    expected = {
        "revision.submitted",
        "revision.rejected",
        "revision.approved",
        "revision.released",
    }
    assert expected <= DOCUMENT_ACTIONS.keys()
    assert all(DOCUMENT_ACTIONS[action][0] == "qms_document_revision" for action in expected)
    assert {"effective_date", "review_date"} <= DOCUMENT_REVISION_AUDIT_FIELDS


def test_risk_audit_rejects_raw_narrative_and_requires_transition_decision() -> None:
    common = {
        "tenant_id": uuid4(),
        "actor_user_id": uuid4(),
        "actor_display_name": "Reviewer",
        "actor_role": "member",
        "resource_id": uuid4(),
        "request_id": uuid4(),
    }
    values = dict.fromkeys(RISK_AUDIT_FIELDS)
    assert set(RISK_ACTIONS.values()) == {"qms_risk"}
    with pytest.raises(AuditPayloadError):
        record_risk(
            Session(),
            action="risk.created",
            new_values={**values, "description": "private"},
            **common,
        )
    with pytest.raises(AuditPayloadError):
        record_risk(Session(), action="risk.transitioned", new_values=values, **common)
    event = record_risk(
        Session(),
        action="risk.transitioned",
        new_values={**values, "decision": "Assessed"},
        **common,
    )
    assert event.resource_type == "qms_risk"


def test_ncr_audit_rejects_unhashed_investigation_and_requires_transition_decision() -> None:
    common = {
        "tenant_id": uuid4(),
        "actor_user_id": uuid4(),
        "actor_display_name": "Reviewer",
        "actor_role": "member",
        "resource_id": uuid4(),
        "request_id": uuid4(),
    }
    values = dict.fromkeys(NCR_AUDIT_FIELDS)
    with pytest.raises(AuditPayloadError):
        record_ncr(
            Session(),
            action="ncr.created",
            new_values={**values, "root_cause_summary": "private"},
            **common,
        )
    with pytest.raises(AuditPayloadError):
        record_ncr(Session(), action="ncr.transitioned", new_values=values, **common)
    event = record_ncr(
        Session(),
        action="ncr.transitioned",
        new_values={**values, "decision": "Investigation started"},
        **common,
    )
    assert event.resource_type == "qms_nonconformity"


@pytest.mark.parametrize(
    "kind,extra",
    [
        ("risk", {"risk_id"}),
        ("control", {"control_instance_id"}),
        ("evidence", {"evidence_id", "control_instance_id"}),
        ("document", {"document_id", "document_revision_id", "snapshot_revision", "file_sha256"}),
    ],
)
def test_ncr_link_audit_keeps_removal_reason_private_and_target_contract_exact(
    kind: str, extra: set[str]
) -> None:
    common = {
        "tenant_id": uuid4(),
        "actor_user_id": uuid4(),
        "actor_display_name": "Maintainer",
        "actor_role": "member",
        "resource_id": uuid4(),
        "request_id": uuid4(),
    }
    values = dict.fromkeys(NCR_LINK_COMMON_FIELDS | extra)
    action = f"ncr.{kind}_unlinked"
    assert NCR_LINK_ACTIONS[action] == "qms_ncr_link"
    with pytest.raises(AuditPayloadError):
        record_ncr_link(
            Session(), action=action, new_values={**values, "removal_reason": "private"}, **common
        )
    with pytest.raises(AuditPayloadError):
        record_ncr_link(
            Session(),
            action=action,
            new_values={**values, "unrelated_target_id": str(uuid4())},
            **common,
        )
    event = record_ncr_link(
        Session(), action=action, old_values=values, new_values=values, **common
    )
    assert event.resource_type == "qms_ncr_link"
