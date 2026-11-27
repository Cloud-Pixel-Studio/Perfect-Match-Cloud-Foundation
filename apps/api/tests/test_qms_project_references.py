"""Supporting-record public contracts; database behavior lives in the integrity suite."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from pmc_api.main import app

ROOT = f"/qms-projects/{uuid4()}/steps/{uuid4()}"


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize("command", ["list", "candidates", "add", "remove"])
def test_reference_route_requires_server_session(kind: str, command: str) -> None:
    path = ROOT + f"/{kind}-" + ("candidates" if command == "candidates" else "links")
    if command == "remove":
        path += f"/{uuid4()}/remove"
    response = TestClient(app).request(
        "GET" if command in {"list", "candidates"} else "POST",
        path,
        json={} if command in {"add", "remove"} else None,
    )
    assert response.status_code == 401


def body(kind: str) -> dict[str, object]:
    return {
        "expected_project_version": 1,
        "expected_step_version": 1,
        "rationale": "Useful support",
        **(
            {
                "document_id": uuid4(),
                "document_revision_id": uuid4(),
                "expected_document_version": 1,
                "expected_revision_version": 1,
            }
            if kind == "document"
            else {
                "evidence_id": uuid4(),
                "expected_instance_version": 1,
                "expected_evidence_version": 1,
            }
        ),
    }


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", str(uuid4())),
        ("snapshot_code", "forged"),
        ("kind", "url"),
        ("expected_project_version", True),
        ("expected_step_version", 0),
        ("rationale", "\ufeff \t"),
        ("rationale", "x" * 501),
    ],
)
def test_input_rejects_forged_scope_and_invalid_contract(
    kind: str, field: str, value: object
) -> None:
    from pmc_api.qms_project_references import DocumentLinkInput, EvidenceLinkInput

    model = DocumentLinkInput if kind == "document" else EvidenceLinkInput
    with pytest.raises(ValidationError):
        model.model_validate({**body(kind), field: value})


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_selected_container_and_target_versions_are_required(kind: str) -> None:
    from pmc_api.qms_project_references import DocumentLinkInput, EvidenceLinkInput

    model = DocumentLinkInput if kind == "document" else EvidenceLinkInput
    source = body(kind)
    for key in [k for k in source if k.startswith("expected_")]:
        with pytest.raises(ValidationError):
            model.model_validate({k: v for k, v in source.items() if k != key})
        with pytest.raises(ValidationError):
            model.model_validate({**source, key: False})


@pytest.mark.parametrize("reason", ["", "\ufeff", "\v\u001c\u3000", "x" * 501])
def test_remove_rejects_blank_or_oversized_reason(reason: str) -> None:
    from pmc_api.qms_project_references import LinkRemove

    with pytest.raises(ValidationError):
        LinkRemove(
            expected_project_version=1,
            expected_step_version=1,
            expected_link_version=1,
            reason=reason,
        )


def test_reference_normalization_counts_unicode_codepoints() -> None:
    from pmc_api.qms_project_references import DocumentLinkInput, LinkRemove

    rationale = "🧭" * 500
    assert (
        DocumentLinkInput.model_validate(
            {**body("document"), "rationale": "\ufeff" + rationale + "\u3000"}
        ).rationale
        == rationale
    )
    assert (
        LinkRemove(
            expected_project_version=1,
            expected_step_version=1,
            expected_link_version=1,
            reason="\ufeffWhy\ufeff",
        ).reason
        == "Why"
    )


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_typed_reference_audit_rejects_raw_narratives_missing_fields_and_wrong_kind(
    kind: str,
) -> None:
    from pmc_api.audit_service import AuditPayloadError, record_qms_project_reference

    common = {
        "tenant_id": uuid4(),
        "actor_user_id": uuid4(),
        "actor_display_name": "Synthetic",
        "actor_role": "member",
        "resource_id": uuid4(),
        "request_id": uuid4(),
    }
    for values in (
        {},
        {"rationale": "private"},
        {"snapshot_name": "private"},
        {"removal_reason": "private"},
    ):
        with pytest.raises(AuditPayloadError):
            record_qms_project_reference(
                Session(), action=f"qms_project.{kind}_linked", new_values=values, **common
            )
    with pytest.raises(AuditPayloadError):
        record_qms_project_reference(
            Session(), action="qms_project.url_linked", new_values={}, **common
        )


@pytest.mark.parametrize("value", ["\x00", "bad\ud800"])
def test_reference_text_rejects_postgres_unsupported_unicode(value: str) -> None:
    from pydantic import TypeAdapter

    from pmc_api.qms_project_references import DocumentLinkInput, LinkRemove, Search

    with pytest.raises(ValidationError):
        DocumentLinkInput.model_validate({**body("document"), "rationale": value})
    with pytest.raises(ValidationError):
        LinkRemove(
            expected_project_version=1,
            expected_step_version=1,
            expected_link_version=1,
            reason=value,
        )
    with pytest.raises(ValidationError):
        TypeAdapter(Search).validate_python(value)


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_versions_reject_values_outside_postgresql_integer(kind: str) -> None:
    from pmc_api.qms_project_references import DocumentLinkInput, EvidenceLinkInput

    model = DocumentLinkInput if kind == "document" else EvidenceLinkInput
    source = body(kind)
    for key in [k for k in source if k.startswith("expected_")]:
        with pytest.raises(ValidationError):
            model.model_validate({**source, key: 2147483648})
