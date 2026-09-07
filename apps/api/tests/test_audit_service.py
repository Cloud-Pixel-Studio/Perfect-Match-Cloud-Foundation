from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from pmc_api.audit_service import AuditPayloadError, record


def test_audit_service_rejects_secret_fields() -> None:
    with pytest.raises(AuditPayloadError):
        record(
            Session(),
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            actor_display_name="A",
            actor_role="owner",
            action="auth.tenant_selected",
            resource_type="session",
            resource_id=uuid4(),
            request_id=uuid4(),
            new_values={"access_token": "synthetic"},
        )


def test_audit_service_rejects_unknown_actions() -> None:
    with pytest.raises(AuditPayloadError):
        record(
            Session(),
            tenant_id=uuid4(),
            actor_user_id=uuid4(),
            actor_display_name="A",
            actor_role="owner",
            action="client.arbitrary",
            resource_type="session",
            resource_id=None,
            request_id=uuid4(),
        )
