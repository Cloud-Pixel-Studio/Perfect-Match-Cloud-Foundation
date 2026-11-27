"""Document evidence references for party requirements in disposable PostgreSQL."""

import os
from typing import Any

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


def allow_document_read(case: Boundary, role: str) -> None:
    case.call(
        "POST",
        "/qms-access/grants",
        {"user_id": str(USERS[role]), "unit_id": str(SITE), "capability": "documents.read"},
        expected=201,
    )


def citation(source: dict[str, str], version: int) -> dict[str, Any]:
    return {
        "expected_party_version": version,
        "expected_document_version": 1,
        "expected_revision_version": 1,
        "requirement_id": DECIDED["id"],
        "document_id": source["document"],
        "document_revision_id": source["revision"],
        "rationale": "The released procedure describes how received lots are checked.",
    }


def test_released_document_reference_survives_changes_and_withdrawal(boundary: Boundary) -> None:
    party = create_party(boundary)
    allow_document_read(boundary, "member")
    source = sources(boundary)
    root = f"{ENDPOINT}/{party['id']}"
    link_path = f"{root}/document-links?unit_id={SITE}"
    boundary.call(
        "POST",
        f"{root}/review?unit_id={SITE}",
        {**DECISION, "expected_version": 1},
        role="admin",
    )
    candidate_response = boundary.call(
        "GET", f"{root}/document-candidates?unit_id={SITE}&q=Source", role="member"
    )
    candidate = candidate_response["items"][0]
    assert candidate["document_id"] == source["document"] and candidate["id"] == source["revision"]
    assert len(candidate_response["items"]) == 1 and not candidate_response["has_more"]
    receipt = boundary.call(
        "POST",
        link_path,
        citation(source, 2),
        role="member",
        expected=201,
    )
    assert receipt["party_version"] == 3
    record = boundary.call("GET", f"{root}?unit_id={SITE}", role="member")
    assert record["status"] == "draft" and record["party_requirements"] == [DECIDED]
    assert "document_id" not in record
    boundary.call("GET", link_path, role="admin", expected=403)
    with boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        assert db.scalar(text("SELECT count(*) FROM public.qms_party_document_links")) == 0
    allow_document_read(boundary, "admin")
    saved = boundary.call("GET", link_path, role="admin")["items"][0]
    assert saved["id"] == receipt["link_id"] and saved["document_state"] == "current"
    assert saved["revision"] == candidate["revision"] and len(saved["file_sha256"]) == 64
    assert saved["requirement_snapshot"] == DECIDED and saved["requirement_current"]
    assert "object_key" not in saved and "storage_key" not in saved
    boundary.call("POST", link_path, citation(source, 3), role="admin", expected=403)
    with boundary.admin.begin() as db:
        db.execute(text("SET LOCAL session_replication_role=replica"))
        db.execute(
            text(
                "UPDATE public.qms_document_revisions SET status='superseded',row_version=2 "
                "WHERE id=:id"
            ),
            {"id": source["revision"]},
        )
    historical = boundary.call("GET", link_path, role="member")["items"][0]
    assert historical["document_state"] == "superseded"
    assert historical["file_sha256"] == saved["file_sha256"]
    boundary.call(
        "POST",
        f"{root}/document-links/{saved['id']}/remove?unit_id={SITE}",
        {"expected_party_version": 3, "reason": "The procedure was superseded."},
        role="member",
    )
    withdrawn = boundary.call("GET", link_path, role="member")["items"][0]
    assert withdrawn["removed_party_version"] == 4
    assert withdrawn["removal_reason"] == "The procedure was superseded."
    assert withdrawn["document_revision_id"] == saved["document_revision_id"]
    blocked = migrate("0054_qms_party_process_links", "downgrade")
    assert blocked.returncode and "cannot discard party document link history" in blocked.stderr


def test_rejects_unreleased_unscreened_cross_scope_and_stale_sources(boundary: Boundary) -> None:
    party = create_party(boundary)
    source = sources(boundary, suffix="clean")
    root = f"{ENDPOINT}/{party['id']}"
    action = f"{root}/document-links?unit_id={SITE}"
    body = citation(source, 1)
    boundary.call("POST", action, body, role="member", expected=403)
    allow_document_read(boundary, "member")
    dirty = sources(
        boundary, suffix="quarantine", revision_status="draft", file_state="quarantined"
    )
    draft = sources(boundary, suffix="draft-clean", revision_status="draft")
    older = sources(boundary, suffix="older", revision_status="superseded")
    outside = sources(boundary, tenant=B, unit=B_SITE, suffix="foreign")
    choices = boundary.call("GET", f"{root}/document-candidates?unit_id={SITE}", role="member")
    assert [item["document_id"] for item in choices["items"]] == [source["document"]]
    invalid = (
        citation(dirty, 1),
        citation(draft, 1),
        citation(older, 1),
        citation(outside, 1),
        {**body, "document_revision_id": dirty["revision"]},
        {**body, "expected_revision_version": 2},
        {**body, "expected_document_version": 2},
    )
    for payload in invalid:
        boundary.call("POST", action, payload, role="member", expected=409)
    assert (
        boundary.clients["member"].post(action, json=body, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    ok = boundary.call("POST", action, body, role="member", expected=201)
    assert ok["party_version"] == 2
    boundary.call("POST", action, citation(source, 2), role="member", expected=409)
    assert len(boundary.call("GET", action, role="member")["items"]) == 1
