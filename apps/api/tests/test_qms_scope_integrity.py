"""Review and retain the declared QMS scope within a company and unit."""

import os
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_qms_context_integrity import BODY, ISSUES, grant
from test_qms_party_requirements_integrity import DECIDED, ENDPOINT, PARTY
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


def review_source(
    case: Boundary, path: str, content: dict[str, object], *, unit: UUID = SITE
) -> dict[str, Any]:
    draft = case.call("POST", path, {**content, "unit_id": str(unit)}, role="member", expected=201)
    return cast(
        dict[str, Any],
        case.call(
            "POST",
            f"{path}/{draft['id']}/review?unit_id={unit}",
            {**APPROVAL, "expected_version": 1},
            role="admin",
        ),
    )


def test_approved_scope_retains_exact_reviewed_basis_and_history(boundary: Boundary) -> None:
    grant_scope_roles(boundary)
    issue = review_source(boundary, ISSUES, dict(BODY))
    party = review_source(boundary, ENDPOINT, {**PARTY, "party_requirements": [DECIDED]})
    refs = [
        {"record_id": issue["id"], "source_version": 2},
        {"record_id": party["id"], "source_version": 2, "requirement_id": DECIDED["id"]},
    ]
    draft = boundary.call(
        "POST",
        PATH,
        {**FIELDS, "scope_basis": refs, "unit_id": str(SITE)},
        role="member",
        expected=201,
    )
    captured = draft["scope_basis"]
    assert captured[0] == {
        **refs[0],
        "requirement_id": None,
        "kind": "issues",
        "code": issue["code"],
        "name": issue["name"],
        "requirement_statement": None,
    }
    assert captured[1] == {
        **refs[1],
        "kind": "interested-parties",
        "code": party["code"],
        "name": party["name"],
        "requirement_statement": DECIDED["statement"],
    }
    base = f"{PATH}/{draft['id']}"
    approval = f"{base}/review?unit_id={SITE}"
    boundary.call("POST", approval, {**APPROVAL, "expected_version": 1}, role="admin")
    revised_issue = {key: value for key, value in BODY.items() if key != "unit_id"}
    boundary.call(
        "PATCH",
        f"{ISSUES}/{issue['id']}?unit_id={SITE}",
        {**revised_issue, "name": "Updated issue title", "expected_version": 2},
        role="member",
    )
    legacy_edit = boundary.call(
        "PATCH", f"{base}?unit_id={SITE}", {**FIELDS, "expected_version": 2}, role="member"
    )
    assert legacy_edit["scope_basis"] == captured
    new_draft = boundary.call(
        "PATCH",
        f"{base}?unit_id={SITE}",
        {**FIELDS, "expected_version": 3, "scope_basis": []},
        role="member",
    )
    assert new_draft["scope_basis"] == []
    current = f"{PATH}/current?unit_id={SITE}"
    assert boundary.call("GET", current, role="auditor")["scope_basis"] == captured
    boundary.call("POST", approval, {**APPROVAL, "expected_version": 4}, role="admin")
    assert boundary.call("GET", current, role="auditor")["scope_basis"] == []
    history = boundary.call("GET", f"{base}/history?unit_id={SITE}", role="auditor")
    assert (
        next(row for row in history if row["snapshot"]["row_version"] == 2)["snapshot"][
            "scope_basis"
        ]
        == captured
    )
    blocked = migrate("0058_qms_scope", "downgrade")
    assert blocked.returncode and "cannot discard QMS scope basis history" in blocked.stderr


def test_scope_basis_rejects_unreviewed_wrong_unit_and_out_of_scope_requirements(
    boundary: Boundary,
) -> None:
    grant_scope_roles(boundary)
    issue = review_source(boundary, ISSUES, dict(BODY))
    other_id = UUID(
        boundary.call(
            "POST",
            "/organization/units",
            {"unit_type": "department", "code": "OTHER", "name": "Other department"},
            expected=201,
        )["id"]
    )
    grant(boundary, "member", "read", "manage", unit=other_id)
    grant(boundary, "admin", "read", "review", unit=other_id)
    other = review_source(boundary, ISSUES, dict(BODY), unit=other_id)
    excluded = {**DECIDED, "id": str(uuid4()), "disposition": "outside_qms"}
    party = review_source(boundary, ENDPOINT, {**PARTY, "party_requirements": [DECIDED, excluded]})
    draft = {**FIELDS, "unit_id": str(SITE)}
    issued = {"record_id": issue["id"], "source_version": 2}
    for rejected in (
        {**issued, "source_version": 1},
        {**issued, "record_id": other["id"]},
        {**issued, "requirement_id": DECIDED["id"]},
        {**issued, "record_id": party["id"]},
        {**issued, "record_id": party["id"], "requirement_id": excluded["id"]},
    ):
        boundary.call(
            "POST", PATH, {**draft, "scope_basis": [rejected]}, role="member", expected=409
        )
    boundary.call(
        "POST", PATH, {**draft, "scope_basis": [issued, issued]}, role="member", expected=422
    )
    boundary.call(
        "POST",
        PATH,
        {**draft, "scope_basis": [{**issued, "name": "Forged title"}]},
        role="member",
        expected=422,
    )
    assert boundary.call("GET", f"{PATH}?unit_id={SITE}", role="member") == []
