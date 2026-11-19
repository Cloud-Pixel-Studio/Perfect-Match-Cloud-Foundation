"""Public project routes and request contracts without a database."""

from fastapi.testclient import TestClient

from pmc_api.main import app


def test_project_route_requires_authenticated_server_session() -> None:
    # Removing route registration would expose 404 instead of its auth boundary.
    response = TestClient(app).get("/qms-projects?unit_id=10000000-0000-4000-8000-000000000001")
    assert response.status_code == 401


def test_typed_project_audit_rejects_missing_fields_and_raw_notes() -> None:
    from uuid import uuid4

    import pytest
    from sqlalchemy.orm import Session

    from pmc_api.audit_service import AuditPayloadError, record_qms_project

    common = {
        "tenant_id": uuid4(),
        "actor_user_id": uuid4(),
        "actor_display_name": "Synthetic actor",
        "actor_role": "member",
        "resource_id": uuid4(),
        "request_id": uuid4(),
    }
    for values in ({}, {"notes": "Private narrative"}, {"reason": "Private reason"}):
        with pytest.raises(AuditPayloadError):
            record_qms_project(Session(), action="qms_project.created", new_values=values, **common)
