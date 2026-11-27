"""Review and retain the declared QMS scope within a company and unit."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_qms_context_integrity import grant
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, Boundary, context, migrate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)

PATH = "/context/qms-scope"
DEFINITION = {
    "products_services": "Assembly and inspection of demonstration components.",
    "basis": "Receiving disruption CTX-01 and customer traceability requirement REQ-04.",
    "applicability": "exceptions",
    "non_applicability": "8.3: Customers provide the designs; the unit builds to specification.",
}
FIELDS = {
    "code": "QMS-SCOPE",
    "name": "Assembly quality management system",
    "classification": "declared_scope",
    "relevance": "relevant",
    "description": "Receiving through dispatch at the assembly unit.",
    "scope_definition": DEFINITION,
    "owner_user_id": str(USERS["member"]),
    "review_due_on": "2099-05-01",
}
APPROVAL = {
    "note": "The boundaries and applicability were checked against contracts and operations.",
    "review_due_on": "2099-06-01",
}


def grant_scope_roles(case: Boundary) -> None:
    grant(case, "member", "read", "manage", "review")
    grant(case, "admin", "read", "review")
    grant(case, "auditor", "read")


def test_only_independently_approved_scope_is_effective(boundary: Boundary) -> None:
    grant_scope_roles(boundary)
    current = f"{PATH}/current?unit_id={SITE}"
    assert boundary.call("GET", current, role="auditor") is None
    response = boundary.clients["member"].post(PATH, json={**FIELDS, "unit_id": str(SITE)})
    assert response.status_code == 201, response.text
    record = response.json()
    assert response.headers["Cache-Control"] == "private, no-store"
    assert record["scope_definition"] == DEFINITION
    base = f"{PATH}/{record['id']}"
    approval = f"{base}/review?unit_id={SITE}"
    boundary.call("POST", PATH, {**FIELDS, "unit_id": str(SITE)}, role="member", expected=409)
    boundary.call(
        "POST", approval, {**APPROVAL, "expected_version": 1}, role="member", expected=403
    )
    boundary.call("POST", approval, {**APPROVAL, "expected_version": 1}, role="admin")
    assert boundary.call("GET", current, role="auditor")["row_version"] == 2

    updated = {
        **FIELDS,
        "description": "Receiving through dispatch, including the new packaging line.",
        "expected_version": 2,
    }
    draft = boundary.call("PATCH", f"{base}?unit_id={SITE}", updated, role="member")
    assert draft["status"] == "draft" and draft["row_version"] == 3
    effective = boundary.call("GET", current, role="auditor")
    assert effective["row_version"] == 2 and effective["description"] == FIELDS["description"]
    boundary.call("POST", approval, {**APPROVAL, "expected_version": 2}, role="admin", expected=409)
    boundary.call("POST", approval, {**APPROVAL, "expected_version": 3}, role="admin")
    effective = boundary.call("GET", current, role="auditor")
    assert effective["row_version"] == 4 and effective["description"] == updated["description"]
    rows = boundary.call("GET", f"{base}/history?unit_id={SITE}", role="auditor")
    assert [row["command"] for row in rows] == ["reviewed", "updated", "reviewed", "created"]
    assert rows[2]["snapshot"]["scope_definition"] == DEFINITION
    boundary.call(
        "POST",
        f"{base}/retire?unit_id={SITE}",
        {"expected_version": 4, "note": "Withdrawal attempted."},
        role="member",
        expected=409,
    )
    blocked = migrate("0057_qms_party_risk_links", "downgrade")
    assert blocked.returncode and "cannot discard declared QMS scope history" in blocked.stderr


def test_requirements_and_authority_are_enforced_at_api_and_database(boundary: Boundary) -> None:
    grant_scope_roles(boundary)
    scope = {**FIELDS, "unit_id": str(SITE)}
    missing_justification = {**DEFINITION, "non_applicability": ""}
    incomplete = {**scope, "scope_definition": missing_justification}
    draft = boundary.call("POST", PATH, incomplete, role="member", expected=201)
    base = f"{PATH}/{draft['id']}"
    current = f"{PATH}/current?unit_id={SITE}"
    body = {**APPROVAL, "expected_version": 1}
    boundary.call("POST", f"{base}/review?unit_id={SITE}", body, role="admin", expected=409)
    boundary.call("GET", current, role="owner", expected=403)
    boundary.call("GET", f"{PATH}/current?unit_id={B_SITE}", role="auditor", expected=403)
    assert boundary.call("GET", current, role="auditor") is None
    assert (
        boundary.clients["admin"]
        .post(f"{base}/review?unit_id={SITE}", json=body, headers={"X-CSRF-Token": ""})
        .status_code
        == 403
    )
    with pytest.raises(DBAPIError) as use_invalid_scope, boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        db.execute(text("SELECT set_config('app.qms_context_command','reviewed',true)"))
        db.execute(
            text(
                "UPDATE qms_context_records SET row_version=2,decision_note='Invalid approval' "
                "WHERE id=:id"
            ),
            {"id": draft["id"]},
        )
    assert "qms_context_scope_definition" in str(use_invalid_scope.value)
