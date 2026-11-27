"""Risk and opportunity citations in a disposable PostgreSQL fixture."""

import os
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import text
from test_qms_party_process_links_integrity import create_party
from test_qms_party_requirements_integrity import DECIDED, DECISION, ENDPOINT
from test_tenant_suspension_integrity import SITE, USERS, Boundary, context, migrate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)


def allow_risk_access(case: Boundary, role: str, *capabilities: str, unit: UUID = SITE) -> None:
    for capability in capabilities:
        case.call(
            "POST",
            "/qms-access/grants",
            {"user_id": str(USERS[role]), "unit_id": str(unit), "capability": capability},
            expected=201,
        )


def create_risk(
    case: Boundary,
    code: str,
    *,
    opportunity: bool = False,
    unit: UUID = SITE,
    process_id: str | None = None,
) -> dict[str, Any]:
    values = (
        {
            "risk_type": "opportunity",
            "response_strategy": "enhance",
            "benefit": "Earlier confirmation of material certificates.",
            "opportunity_action": "Link supplier certificates to receiving lots.",
        }
        if opportunity
        else {}
    )
    return cast(
        dict[str, Any],
        case.call(
            "POST",
            "/risks",
            {
                "unit_id": str(unit),
                "process_id": process_id or case.process,
                "code": code,
                "name": "Synthetic receiving record",
                "description": "Timeliness of the supplier certificate during receiving.",
                **values,
            },
            role="member",
            expected=201,
        ),
    )


def transition_risk(case: Boundary, risk: dict[str, Any], target: str) -> dict[str, Any]:
    notes = {"closure_notes": "Receiving confirmed the result."} if target == "closed" else {}
    return cast(
        dict[str, Any],
        case.call(
            "POST",
            f"/risks/{risk['id']}/transition",
            {
                "expected_version": risk["row_version"],
                "target_state": target,
                "decision": "Reviewed against the receiving process.",
                **notes,
            },
            role="member",
        ),
    )


def risk_citation(risk: dict[str, Any], party_version: int) -> dict[str, object]:
    return {
        "expected_party_version": party_version,
        "expected_risk_version": risk["row_version"],
        "requirement_id": DECIDED["id"],
        "risk_id": risk["id"],
        "rationale": "The receiving review addresses the certificate requirement.",
    }


def test_closed_opportunity_keeps_cited_state_and_withdrawal_history(boundary: Boundary) -> None:
    party = create_party(boundary)
    allow_risk_access(boundary, "member", "risks.read", "risks.manage", "risks.review")
    opportunity = transition_risk(
        boundary, create_risk(boundary, "OPP-01", opportunity=True), "assessed"
    )
    root = f"{ENDPOINT}/{party['id']}"
    action = f"{root}/risk-links?unit_id={SITE}"
    boundary.call(
        "POST", f"{root}/review?unit_id={SITE}", {**DECISION, "expected_version": 1}, role="admin"
    )
    candidate = boundary.call("GET", f"{root}/risk-candidates?unit_id={SITE}&q=OPP", role="member")[
        "items"
    ][0]
    assert candidate["id"] == opportunity["id"] and candidate["risk_type"] == "opportunity"
    receipt = boundary.call(
        "POST", action, risk_citation(opportunity, 2), role="member", expected=201
    )
    assert receipt["party_version"] == 3
    assert boundary.call("GET", f"{root}?unit_id={SITE}", role="member")["status"] == "draft"
    boundary.call("GET", action, role="admin", expected=403)
    with boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        assert db.scalar(text("SELECT count(*) FROM public.qms_party_risk_links")) == 0
    allow_risk_access(boundary, "admin", "risks.read")
    linked = boundary.call("GET", action, role="admin")["items"][0]
    assert linked["id"] == receipt["link_id"] and linked["requirement_snapshot"] == DECIDED
    assert linked["linked_risk_state"] == linked["risk_state"] == "assessed"
    assert linked["risk_version"] == 2 and not linked["risk_changed"]
    boundary.call("POST", action, risk_citation(opportunity, 3), role="admin", expected=403)

    monitored = transition_risk(boundary, opportunity, "monitoring")
    transition_risk(boundary, monitored, "closed")
    current = boundary.call("GET", action, role="member")["items"][0]
    assert current["risk_state"] == "closed" and current["risk_changed"]
    assert current["linked_risk_state"] == "assessed" and current["risk_version"] == 2
    boundary.call(
        "POST",
        f"{root}/risk-links/{linked['id']}/remove?unit_id={SITE}",
        {"expected_party_version": 3, "reason": "Review completed for this opportunity."},
        role="member",
    )
    withdrawn = boundary.call("GET", action, role="member")["items"][0]
    assert withdrawn["removed_party_version"] == 4
    assert withdrawn["removal_reason"] == "Review completed for this opportunity."
    assert withdrawn["requirement_snapshot"] == DECIDED
    blocked = migrate("0056_qms_party_evidence_links", "downgrade")
    assert blocked.returncode and "cannot discard party risk link history" in blocked.stderr


def test_risk_eligibility_and_versions_are_rechecked_on_save(boundary: Boundary) -> None:
    party = create_party(boundary)
    root = f"{ENDPOINT}/{party['id']}"
    action = f"{root}/risk-links?unit_id={SITE}"
    allow_risk_access(boundary, "member", "risks.read", "risks.manage", "risks.review")
    draft = create_risk(boundary, "RISK-DRAFT")
    active = transition_risk(boundary, create_risk(boundary, "RISK-ACTIVE"), "assessed")
    closed = transition_risk(boundary, create_risk(boundary, "RISK-CLOSED"), "assessed")
    closed = transition_risk(boundary, transition_risk(boundary, closed, "monitoring"), "closed")
    body = risk_citation(active, 1)
    candidates = boundary.call("GET", f"{root}/risk-candidates?unit_id={SITE}", role="member")
    assert [item["id"] for item in candidates["items"]] == [active["id"]]
    for invalid in (
        risk_citation(draft, 1),
        risk_citation(closed, 1),
        {**body, "expected_risk_version": 1},
        {**body, "expected_party_version": 2},
    ):
        boundary.call("POST", action, invalid, role="member", expected=409)
    assert (
        boundary.clients["member"].post(action, json=body, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    boundary.call("POST", action, body, role="member", expected=201)
    boundary.call("POST", action, risk_citation(active, 2), role="member", expected=409)
    assert len(boundary.call("GET", action, role="member")["items"]) == 1


def test_risk_citation_requires_exact_unit_even_with_access_to_both(boundary: Boundary) -> None:
    party = create_party(boundary)
    allow_risk_access(boundary, "member", "risks.read")
    other = UUID(
        boundary.call(
            "POST",
            "/organization/units",
            {"unit_type": "department", "code": "OTHER", "name": "Synthetic other unit"},
            expected=201,
        )["id"]
    )
    allow_risk_access(
        boundary,
        "member",
        "processes.read",
        "processes.manage",
        "risks.read",
        "risks.manage",
        "risks.review",
        unit=other,
    )
    process = boundary.call(
        "POST",
        "/processes",
        {"unit_id": str(other), "code": "OTHER-PROC", "name": "Other process"},
        role="member",
        expected=201,
    )
    risk = transition_risk(
        boundary,
        create_risk(boundary, "RISK-OTHER", unit=other, process_id=process["id"]),
        "assessed",
    )
    root = f"{ENDPOINT}/{party['id']}"
    candidates = boundary.call("GET", f"{root}/risk-candidates?unit_id={SITE}", role="member")
    assert not candidates["items"]
    action = f"{root}/risk-links?unit_id={SITE}"
    boundary.call("POST", action, risk_citation(risk, 1), role="member", expected=409)
    assert boundary.call("GET", action, role="member")["party_version"] == 1
