"""Public project routes and request contracts without a database."""

from uuid import UUID

import pytest
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


@pytest.mark.parametrize(
    "kind",
    ["code", "name", "patch_name", "reason", "blocked_notes", "reported_notes"],
)
def test_project_text_rejects_bom_only_meaningful_fields(kind: str) -> None:
    from pydantic import ValidationError

    from pmc_api.qms_projects import ProjectInput, ProjectPatch, StatusCommand, StepPatch

    body = {
        "unit_id": "10000000-0000-4000-8000-000000000001",
        "code": "PLAN",
        "name": "Plan",
        "journey_key": "initial",
    }
    with pytest.raises(ValidationError):
        if kind in {"code", "name"}:
            ProjectInput.model_validate({**body, kind: "\ufeff"})
        elif kind == "patch_name":
            ProjectPatch(expected_version=1, name="\ufeff")
        elif kind == "reason":
            StatusCommand(expected_version=1, target_status="archived", reason="\ufeff")
        else:
            StepPatch(
                expected_project_version=1,
                expected_version=1,
                status="blocked" if kind == "blocked_notes" else "reported",
                notes="\ufeff",
            )


def test_project_identity_trim_precedes_unicode_limits_and_preserves_internal_text() -> None:
    from pmc_api.qms_projects import ProjectInput, StatusCommand, StepPatch

    code, name = "\U0001f9ed" * 40, "\U0001f680" * 160
    project = ProjectInput(
        unit_id=UUID("10000000-0000-4000-8000-000000000001"),
        code="\ufeff\v" + code + "\u3000\ufeff",
        name="\u3000\ufeff" + name + "\ufeff\f",
        journey_key="initial",
    )
    assert project.code == code and project.name == name
    reason = "R" * 500
    command = StatusCommand(
        expected_version=1, target_status="archived", reason="\ufeff" + reason + "\ufeff"
    )
    assert command.reason == reason
    internal = "A\ufeff \t\u2003B"
    project = ProjectInput.model_validate(
        {**project.model_dump(), "code": "\ufeff" + internal + "\ufeff", "name": internal}
    )
    assert project.code == internal and project.name == internal
    notes = "\ufeff\v Trabajo documentado \u3000\ufeff"
    step = StepPatch(expected_project_version=1, expected_version=1, status="reported", notes=notes)
    assert step.notes == notes
