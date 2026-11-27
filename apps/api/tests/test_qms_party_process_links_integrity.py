"""Scoped process links and version history in disposable PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_qms_party_requirements_integrity import DECIDED, DECISION, ENDPOINT, PARTY, assignment
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, Boundary, context, migrate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)


def create_party(boundary: Boundary) -> dict[str, Any]:
    assignment(boundary)
    return cast(
        dict[str, Any],
        boundary.call(
            "POST",
            ENDPOINT,
            {**PARTY, "party_requirements": [DECIDED]},
            role="member",
            expected=201,
        ),
    )


def link_body(case: Boundary, version: int) -> dict[str, object]:
    return {
        "expected_party_version": version,
        "expected_process_version": 1,
        "requirement_id": DECIDED["id"],
        "process_id": case.process,
        "rationale": "Receiving compares the supplier certificate with the lot.",
    }


def test_process_link_reopens_review_and_keeps_both_sources(boundary: Boundary) -> None:
    party = create_party(boundary)
    path = f"{ENDPOINT}/{party['id']}"
    action = f"{path}/process-links?unit_id={SITE}"
    review = boundary.call(
        "POST",
        f"{path}/review?unit_id={SITE}",
        {**DECISION, "expected_version": 1},
        role="admin",
    )
    assert review["status"] == "active"
    catalog = boundary.call(
        "GET", f"{path}/process-candidates?unit_id={SITE}&q=synthetic", role="member"
    )
    assert catalog["items"][0]["id"] == boundary.process and catalog["party_version"] == 2
    no_literal_match = boundary.call(
        "GET", f"{path}/process-candidates?unit_id={SITE}&q=%25", role="member"
    )
    assert no_literal_match["items"] == []
    receipt = boundary.call("POST", action, link_body(boundary, 2), role="member", expected=201)
    assert receipt["party_version"] == 3 and receipt["action"] == "linked"
    updated = boundary.call("GET", f"{path}?unit_id={SITE}", role="member")
    assert updated["status"] == "draft" and updated["reviewed_at"] is None
    assert updated["party_requirements"] == [DECIDED] and "process_id" not in updated

    boundary.call("GET", action, role="admin", expected=403)
    with boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        assert db.scalar(text("SELECT count(*) FROM public.qms_party_process_links")) == 0
    boundary.call(
        "POST",
        "/qms-access/grants",
        {"unit_id": str(SITE), "user_id": str(USERS["admin"]), "capability": "processes.read"},
        expected=201,
    )
    with_access = boundary.call("GET", action, role="admin")
    stored = with_access["items"][0]
    assert stored["id"] == receipt["link_id"] and stored["process_state"] == "current"
    assert stored["requirement_current"] and stored["requirement_snapshot"] == DECIDED
    boundary.call("POST", action, link_body(boundary, 3), role="admin", expected=403)
    boundary.call(
        "PATCH",
        f"/processes/{boundary.process}",
        {"expected_version": 1, "name": "Changed receiving"},
        role="member",
    )
    changed = boundary.call("GET", action, role="member")["items"][0]
    assert changed["process_state"] == "changed"
    assert changed["process_name"] == stored["process_name"]
    boundary.call(
        "POST",
        f"/processes/{boundary.process}/archive",
        {"expected_version": 2},
        role="member",
    )
    archived = boundary.call("GET", action, role="member")["items"][0]
    assert archived["process_state"] == "archived" and archived["process_version"] == 1

    edited = {key: value for key, value in PARTY.items() if key != "unit_id"}
    boundary.call(
        "PATCH",
        f"{path}?unit_id={SITE}",
        {**edited, "expected_version": 3, "party_requirements": []},
        role="member",
    )
    previous = boundary.call("GET", action, role="member")["items"][0]
    assert not previous["requirement_current"] and previous["requirement_snapshot"] == DECIDED
    remove_path = f"{path}/process-links/{stored['id']}/remove?unit_id={SITE}"
    withdrawal = {"expected_party_version": 4, "reason": "Requirement superseded."}
    removed = boundary.call("POST", remove_path, withdrawal, role="member")
    assert removed["action"] == "removed" and removed["party_version"] == 5
    page = boundary.call("GET", action, role="member")
    assert page["items"][0]["removed_party_version"] == 5
    assert page["items"][0]["removal_reason"] == withdrawal["reason"]
    assert page["items"][0]["requirement_snapshot"] == DECIDED
    history = boundary.call("GET", f"{path}/history?unit_id={SITE}", role="member")
    assert [item["snapshot"]["row_version"] for item in history] == [5, 4, 3, 2, 1]
    downgrade = migrate("0053_qms_party_requirements", "downgrade")
    assert downgrade.returncode and "cannot discard party process link history" in downgrade.stderr


def test_invalid_targets_stale_versions_and_competing_writes(boundary: Boundary) -> None:
    party = create_party(boundary)
    path = f"{ENDPOINT}/{party['id']}/process-links"
    action = f"{path}?unit_id={SITE}"
    command = link_body(boundary, 1)
    boundary.call("POST", f"{path}?unit_id={B_SITE}", command, role="member", expected=403)
    for changes in (
        {"expected_process_version": 2},
        {"expected_party_version": 2},
        {"requirement_id": str(uuid4())},
        {"process_id": str(uuid4())},
    ):
        boundary.call("POST", action, {**command, **changes}, role="member", expected=409)
    client = boundary.clients["member"]
    assert client.post(action, json=command, headers={"X-CSRF-Token": ""}).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks = [executor.submit(client.post, action, json=command) for _ in range(2)]
        assert sorted(task.result().status_code for task in tasks) == [201, 409]
    boundary.call("POST", action, link_body(boundary, 2), role="member", expected=409)
    page = boundary.call("GET", action, role="member")
    assert len(page["items"]) == 1 and page["party_version"] == 2
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM public.qms_context_revisions")) == 2
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.audit_events WHERE action='qms_context.updated'")
            )
            == 1
        )


def test_source_scope_is_exact_even_when_actor_can_read_both_units(boundary: Boundary) -> None:
    party = create_party(boundary)
    other = boundary.call(
        "POST",
        "/organization/units",
        {"unit_type": "department", "code": "OTHER", "name": "Synthetic other unit"},
        expected=201,
    )["id"]
    for capability in ("processes.read", "processes.manage"):
        boundary.call(
            "POST",
            "/qms-access/grants",
            {"unit_id": other, "user_id": str(USERS["member"]), "capability": capability},
            expected=201,
        )
    source = boundary.call(
        "POST",
        "/processes",
        {"unit_id": other, "code": "SOURCE-OTHER", "name": "Other process"},
        role="member",
        expected=201,
    )
    base = f"{ENDPOINT}/{party['id']}"
    assert (
        boundary.call(
            "GET",
            f"{base}/process-candidates?unit_id={SITE}&q=SOURCE-OTHER",
            role="member",
        )["items"]
        == []
    )
    boundary.call(
        "POST",
        f"{base}/process-links?unit_id={SITE}",
        {**link_body(boundary, 1), "process_id": source["id"]},
        role="member",
        expected=409,
    )
    assert (
        boundary.call(
            "GET",
            f"{base}?unit_id={SITE}",
            role="member",
        )["row_version"]
        == 1
    )
