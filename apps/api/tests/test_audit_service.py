from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from pmc_api.audit_service import AuditPayloadError, record_tenant_selected, validate_payload


def test_audit_service_rejects_secret_key_variants() -> None:
    variants = [
        "password", "user_password", "userPassword", "session_token", "sessionToken",
        "csrf_token", "authorization_code", "pkce_verifier", "login_binding", "access_token",
        "refresh_token", "id_token", "cookie", "cookie_value", "api_key", "apiKey",
        "private_key", "privateKey", "client_secret", "clientSecret", "database_password",
        "aws_credential", "github_credential", "githubCredential",
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
