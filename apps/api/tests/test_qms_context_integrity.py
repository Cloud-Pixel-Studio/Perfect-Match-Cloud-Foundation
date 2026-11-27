"""Context and interested parties with real PostgreSQL and synthetic sessions."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, A, B, Boundary
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service
from pmc_api.main import app

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)

BODY = {
    "unit_id": str(SITE),
    "code": "CTX-01",
    "name": "Receiving interruptions",
    "classification": "external",
    "category": "environmental",
    "relevance": "relevant",
    "description": "Assess disruptions and review the receiving contingency.",
    "requirements": "Maintain traceability during a receiving interruption.",
    "evidence_summary": "Synthetic tabletop exercise.",
    "owner_user_id": str(USERS["member"]),
    "review_due_on": "2099-05-01",
}
ISSUES = "/context/issues"


def grant(
    boundary: Boundary, role: str, *capabilities: str, unit: UUID = SITE, owner: str = "owner"
) -> None:
    for capability in capabilities:
        boundary.call(
            "POST",
            "/qms-access/grants",
            {
                "user_id": str(USERS[role]),
                "unit_id": str(unit),
                "capability": f"context.{capability}",
            },
            expected=201,
            role=owner,
        )


def test_complete_lifecycle_and_atomic_history(boundary: Boundary) -> None:
    grant(boundary, "member", "read", "manage", "review")
    grant(boundary, "admin", "read", "review")
    grant(boundary, "auditor", "read")
    response = boundary.clients["member"].post(ISSUES, json=BODY)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert response.headers["X-Tenant-ID"] == str(A)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert draft["status"] == "draft" and draft["row_version"] == 1
    assert draft["owner_display_name"] == "Synthetic member"
    assert boundary.call("GET", f"/context/members?unit_id={SITE}", role="member")
    boundary.call("GET", f"/context/members?unit_id={SITE}", role="auditor", expected=403)

    detail = f"{ISSUES}/{draft['id']}"
    review = {
        "expected_version": 1,
        "note": "Verified the assessment.",
        "review_due_on": "2099-06-01",
    }
    boundary.call("POST", f"{detail}/review?unit_id={SITE}", review, role="member", expected=403)
    boundary.call("POST", f"{detail}/review?unit_id={SITE}", review, role="auditor", expected=403)
    assessed = boundary.call("POST", f"{detail}/review?unit_id={SITE}", review, role="admin")
    assert assessed["status"] == "active" and assessed["row_version"] == 2
    assert assessed["updated_by_user_id"] == str(USERS["admin"]) and assessed["reviewed_at"]

    patch: dict[str, object] = {key: value for key, value in BODY.items() if key != "unit_id"}
    patch.update(expected_version=2, evidence_summary="Updated exercise evidence.")
    boundary.call("PATCH", f"{detail}?unit_id={SITE}", patch, role="admin", expected=403)
    updated = boundary.call("PATCH", f"{detail}?unit_id={SITE}", patch, role="member")
    assert updated["status"] == "draft" and updated["reviewed_at"] is None
    boundary.call("PATCH", f"{detail}?unit_id={SITE}", patch, role="member", expected=409)

    retired = boundary.call(
        "POST",
        f"{detail}/retire?unit_id={SITE}",
        {"expected_version": 3, "note": "Replaced by a new assessment."},
        role="member",
    )
    assert retired["status"] == "retired" and retired["row_version"] == 4
    assert boundary.call("GET", f"{ISSUES}?unit_id={SITE}&status=active", role="auditor") == []
    assert boundary.call("GET", f"{detail}?unit_id={SITE}", role="auditor") == retired
    history = boundary.call("GET", f"{detail}/history?unit_id={SITE}", role="auditor")
    assert [row["command"] for row in history] == ["retired", "updated", "reviewed", "created"]
    assert history[2]["snapshot"]["evidence_summary"] == BODY["evidence_summary"]
    assert history[0]["snapshot"]["decision_note"] == "Replaced by a new assessment."
    with boundary.admin.connect() as db:
        assert (
            len(
                list(
                    db.scalars(
                        text("SELECT action FROM audit_events WHERE action LIKE 'qms_context.%'")
                    )
                )
            )
            == 4
        )
        assert db.scalar(text("SELECT count(*) FROM qms_context_revisions")) == 4
        assert db.scalar(
            text(
                "SELECT NOT has_table_privilege('pmcloud_app','qms_context_records','DELETE') "
                "AND NOT has_table_privilege('pmcloud_app','qms_context_revisions','UPDATE') "
                "AND NOT has_table_privilege('pmcloud_app','qms_context_revisions','INSERT')"
            )
        )


def test_tenant_unit_and_csrf_boundaries(boundary: Boundary) -> None:
    with TestClient(app) as anonymous:
        assert anonymous.get(f"{ISSUES}?unit_id={SITE}").status_code == 401
    boundary.call("POST", ISSUES, BODY, expected=403)
    grant(boundary, "member", "read", "manage")
    record = boundary.call("POST", ISSUES, BODY, role="member", expected=201)
    boundary.call("GET", f"{ISSUES}?unit_id={B_SITE}", role="member", expected=403)
    boundary.call("GET", f"{ISSUES}/{record['id']}?unit_id={uuid4()}", role="member", expected=403)
    client = boundary.clients["member"]
    assert client.post(ISSUES, json=BODY, headers={"X-CSRF-Token": ""}).status_code == 403
    boundary.call(
        "GET",
        f"/context/interested-parties/{record['id']}?unit_id={SITE}",
        role="member",
        expected=404,
    )
    with boundary.admin.begin() as db:
        db.execute(
            text(
                "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) "
                "VALUES(:id,:tenant,:user,'member','active',now())"
            ),
            {"id": uuid4(), "tenant": B, "user": USERS["member"]},
        )
        db.execute(
            text(
                "UPDATE application_sessions SET current_tenant_id=:tenant "
                "WHERE user_id IN (:member,:owner)"
            ),
            {"tenant": B, "member": USERS["member"], "owner": USERS["owner"]},
        )
    boundary.call("GET", f"{ISSUES}?unit_id={SITE}", role="member", expected=403)
    boundary.call(
        "GET", f"{ISSUES}/{record['id']}/history?unit_id={SITE}", role="member", expected=403
    )
    boundary.call("POST", ISSUES, BODY, role="member", expected=403)
    grant(boundary, "member", "read", "manage", unit=B_SITE)
    assert boundary.call("GET", f"{ISSUES}?unit_id={B_SITE}", role="member") == []
    boundary.call("GET", f"{ISSUES}/{record['id']}?unit_id={B_SITE}", role="member", expected=404)
    moved = boundary.call(
        "POST", ISSUES, {**BODY, "unit_id": str(B_SITE)}, role="member", expected=201
    )
    assert moved["tenant_id"] == str(B) and moved["id"] != record["id"]


def test_tenant_suspension_closes_the_register(boundary: Boundary) -> None:
    grant(boundary, "member", "read", "manage")
    record = boundary.call("POST", ISSUES, BODY, role="member", expected=201)
    boundary.change("tenant", False)
    boundary.call("GET", f"{ISSUES}?unit_id={SITE}", role="member", expected=403)
    boundary.call(
        "GET", f"{ISSUES}/{record['id']}/history?unit_id={SITE}", role="member", expected=403
    )
    boundary.call("POST", ISSUES, {**BODY, "code": "CTX-02"}, role="member", expected=403)


def test_history_and_audit_are_atomic(boundary: Boundary, monkeypatch: pytest.MonkeyPatch) -> None:
    grant(boundary, "member", "read", "manage")

    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(audit_service, "record_qms_context", unavailable)
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            boundary.clients["member"].post(ISSUES, json=BODY)
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM qms_context_records")) == 0
        assert db.scalar(text("SELECT count(*) FROM qms_context_revisions")) == 0
    boundary.call("POST", ISSUES, BODY, role="member", expected=201)


def test_populated_context_blocks_destructive_downgrade(boundary: Boundary) -> None:
    from test_tenant_suspension_integrity import migrate

    grant(boundary, "member", "read", "manage")
    boundary.call("POST", ISSUES, BODY, role="member", expected=201)
    result = migrate("0051_qms_project_references", "downgrade")
    assert result.returncode != 0 and "cannot discard QMS context history" in result.stderr
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM qms_context_revisions")) == 1
        assert (
            db.scalar(
                text(
                    "SELECT relforcerowsecurity FROM pg_class "
                    "WHERE oid='public.qms_context_records'::regclass"
                )
            )
            is True
        )


def test_interested_parties_and_concurrent_edit(boundary: Boundary) -> None:
    grant(boundary, "member", "read", "manage")
    grant(boundary, "admin", "read", "review")
    endpoint = "/context/interested-parties"
    body = {**BODY, "classification": "supplier", "category": "", "relevance": "under_review"}
    record = boundary.call("POST", endpoint, body, role="member", expected=201)
    boundary.call(
        "POST",
        endpoint,
        {**body, "owner_user_id": str(uuid4()), "code": "CTX-02"},
        role="member",
        expected=409,
    )
    boundary.call("POST", endpoint, {**body, "code": "ctx-01"}, role="member", expected=409)
    path = f"{endpoint}/{record['id']}"
    boundary.call(
        "POST",
        f"{path}/review?unit_id={SITE}",
        {"expected_version": 1, "note": "Relevance undecided.", "review_due_on": "2099-06-01"},
        role="admin",
        expected=409,
    )
    body.pop("unit_id")
    client = boundary.clients["member"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        commands = [
            executor.submit(
                client.patch,
                f"{path}?unit_id={SITE}",
                json={
                    **body,
                    "name": name,
                    "expected_version": 1,
                },
            )
            for name in ("Synthetic vendor A", "Synthetic vendor B")
        ]
        assert sorted(command.result().status_code for command in commands) == [200, 409]
    page = boundary.call("GET", f"{path}/history?unit_id={SITE}&limit=1", role="member")
    assert page[0]["snapshot"]["row_version"] == 2
    older = boundary.call("GET", f"{path}/history?unit_id={SITE}&before_version=2", role="member")
    assert len(older) == 1 and older[0]["command"] == "created"
    assert boundary.call("GET", f"{ISSUES}?unit_id={SITE}", role="member") == []
