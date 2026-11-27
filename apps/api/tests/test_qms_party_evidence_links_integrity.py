"""Accepted operational evidence citations in a disposable PostgreSQL fixture."""

import os

import pytest
from sqlalchemy import text
from test_qms_party_process_links_integrity import create_party
from test_qms_party_requirements_integrity import DECIDED, DECISION, ENDPOINT
from test_qms_project_reference_integrity import sources
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, B, Boundary, context, migrate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)


def allow_evidence_read(case: Boundary, role: str) -> None:
    case.call(
        "POST",
        "/qms-access/grants",
        {"user_id": str(USERS[role]), "unit_id": str(SITE), "capability": "control_instances.read"},
        expected=201,
    )


def evidence_citation(source: dict[str, str], version: int) -> dict[str, object]:
    return {
        "expected_party_version": version,
        "expected_instance_version": 1,
        "expected_evidence_version": 1,
        "requirement_id": DECIDED["id"],
        "control_instance_id": source["instance"],
        "evidence_id": source["evidence"],
        "rationale": "The accepted receiving record shows the completed lot check.",
    }


def test_reviewed_evidence_reference_is_preserved_after_archival(boundary: Boundary) -> None:
    party = create_party(boundary)
    allow_evidence_read(boundary, "member")
    source = sources(boundary)
    root = f"{ENDPOINT}/{party['id']}"
    action = f"{root}/evidence-links?unit_id={SITE}"
    boundary.call(
        "POST",
        f"{root}/review?unit_id={SITE}",
        {**DECISION, "expected_version": 1},
        role="admin",
    )
    candidate = boundary.call(
        "GET",
        f"{root}/evidence-candidates?unit_id={SITE}&q=Evidence",
        role="member",
    )["items"][0]
    assert (
        candidate["id"] == source["evidence"]
        and candidate["control_instance_id"] == source["instance"]
    )
    receipt = boundary.call(
        "POST",
        action,
        evidence_citation(source, 2),
        role="member",
        expected=201,
    )
    assert receipt["party_version"] == 3
    row = boundary.call("GET", f"{root}?unit_id={SITE}", role="member")
    assert row["status"] == "draft" and row["party_requirements"] == [DECIDED]
    assert "evidence_id" not in row
    boundary.call("GET", action, role="admin", expected=403)
    with boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        assert db.scalar(text("SELECT count(*) FROM public.qms_party_evidence_links")) == 0
    allow_evidence_read(boundary, "admin")
    stored = boundary.call("GET", action, role="admin")["items"][0]
    assert stored["id"] == receipt["link_id"] and stored["evidence_state"] == "current"
    assert stored["accepted_at"] and stored["requirement_snapshot"] == DECIDED
    assert stored["evidence_type"] == "record" and "evidence_summary" not in stored
    boundary.call("POST", action, evidence_citation(source, 3), role="admin", expected=403)

    with boundary.admin.begin() as db:
        db.execute(text("SET LOCAL session_replication_role=replica"))
        db.execute(
            text(
                "UPDATE public.qms_control_instances SET status='archived',row_version=2 "
                "WHERE id=:id"
            ),
            {"id": source["instance"]},
        )
    archived = boundary.call("GET", action, role="member")["items"][0]
    assert archived["evidence_state"] == "implementation_archived"
    assert archived["accepted_at"] == stored["accepted_at"] and archived["evidence_version"] == 1
    boundary.call(
        "POST",
        f"{root}/evidence-links/{stored['id']}/remove?unit_id={SITE}",
        {"expected_party_version": 3, "reason": "The implementation was archived."},
        role="member",
    )
    withdrawn = boundary.call("GET", action, role="member")["items"][0]
    assert withdrawn["removed_party_version"] == 4
    assert withdrawn["removal_reason"] == "The implementation was archived."
    assert withdrawn["requirement_snapshot"] == DECIDED
    blocked = migrate("0055_qms_party_document_links", "downgrade")
    assert blocked.returncode and "cannot discard party evidence link history" in blocked.stderr


def test_evidence_eligibility_and_scope_are_checked_on_save(boundary: Boundary) -> None:
    party = create_party(boundary)
    root = f"{ENDPOINT}/{party['id']}"
    action = f"{root}/evidence-links?unit_id={SITE}"
    source = sources(boundary, suffix="accepted")
    body = evidence_citation(source, 1)
    boundary.call("POST", action, body, role="member", expected=403)
    allow_evidence_read(boundary, "member")
    draft = sources(boundary, suffix="draft", evidence_status="draft")
    rejected = sources(boundary, suffix="rejected", evidence_status="rejected")
    foreign = sources(boundary, tenant=B, unit=B_SITE, suffix="foreign")
    available = boundary.call("GET", f"{root}/evidence-candidates?unit_id={SITE}", role="member")
    assert [item["id"] for item in available["items"]] == [source["evidence"]]
    for invalid in (
        evidence_citation(draft, 1),
        evidence_citation(rejected, 1),
        evidence_citation(foreign, 1),
        {**body, "control_instance_id": draft["instance"]},
        {**body, "expected_instance_version": 2},
        {**body, "expected_evidence_version": 2},
    ):
        boundary.call("POST", action, invalid, role="member", expected=409)
    assert (
        boundary.clients["member"].post(action, json=body, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    reply = boundary.call("POST", action, body, role="member", expected=201)
    assert reply["party_version"] == 2
    boundary.call("POST", action, evidence_citation(source, 2), role="member", expected=409)
    assert len(boundary.call("GET", action, role="member")["items"]) == 1
