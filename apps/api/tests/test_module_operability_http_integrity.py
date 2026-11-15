"""Positive HTTP boundaries against disposable SQL, with explicit in-memory AV/S3.

Sessions, CSRF, capability checks, command handlers, ledger and RLS are real.
No OIDC exchange, external antivirus or object storage is contacted.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

import httpx
import pytest
from sqlalchemy import text
from test_tenant_suspension_integrity import SITE, USERS, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service, documents
from pmc_api.antivirus import ScanVerdict

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires dedicated disposable PostgreSQL, never a running application database",
    ),
]
PDF = b"%PDF-1.7\nSynthetic operability fixture.\n%%EOF\n"


@pytest.fixture(autouse=True)
def record_http_observations(boundary: Boundary, request: pytest.FixtureRequest) -> Iterator[None]:
    """Record only synthetic method/path/status metadata, never tokens or bodies."""
    operations: list[dict[str, str | int]] = []
    for role, client in boundary.clients.items():

        def observe(response: httpx.Response, actor_role: str = role) -> None:
            operations.append(
                {
                    "role": actor_role,
                    "method": response.request.method,
                    "path": response.request.url.path,
                    "status": response.status_code,
                }
            )

        client.event_hooks["response"].append(observe)
    yield
    output = os.environ.get("PMC_HTTP_AUDIT_OUTPUT")
    if output:
        path = Path(output)
        prior = json.loads(path.read_text()) if path.exists() else []
        prior.append({"test_id": request.node.nodeid, "operations": operations})
        path.write_text(json.dumps(prior, indent=2) + "\n")


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def create_bucket(self, bucket: str) -> None:
        pass

    def put_object(self, bucket: str, key: str, body: BinaryIO) -> None:
        self.objects[bucket, key] = body.read()

    def get_object(self, bucket: str, key: str) -> bytes:
        return self.objects[bucket, key]

    def delete_object(self, bucket: str, key: str) -> None:
        del self.objects[bucket, key]


def grant(case: Boundary, role: str, *capabilities: str) -> None:
    for capability in capabilities:
        case.call(
            "POST",
            "/qms-access/grants",
            {"user_id": str(USERS[role]), "unit_id": str(SITE), "capability": capability},
            expected=201,
        )


def document(
    case: Boundary, monkeypatch: pytest.MonkeyPatch, *, combined_reviewer: bool = False
) -> tuple[dict[str, Any], dict[str, Any], MemoryStorage]:
    grant(
        case,
        "member",
        "documents.read",
        "documents.author",
        "documents.review",
        "documents.approve",
        "documents.release",
    )
    grant(case, "admin", "documents.read", "documents.review", "documents.approve")
    # Positive lifecycle fixtures explicitly use a combined reviewer/releaser.
    # Minimal review/approval authority is preserved separately as a strict XFAIL.
    if combined_reviewer:
        grant(case, "admin", "documents.release")
    storage = MemoryStorage()
    monkeypatch.setattr(documents, "get_object_storage", lambda: storage)
    monkeypatch.setattr(documents, "scan", lambda _payload: ScanVerdict.CLEAN)
    doc = case.call(
        "POST",
        "/documents",
        {
            "unit_id": str(SITE),
            "process_id": case.process,
            "code": "HTTP-DOC",
            "title": "Synthetic controlled procedure",
            "document_type": "procedure",
            "owner_user_id": str(USERS["member"]),
        },
        role="member",
        expected=201,
    )
    revision = case.call(
        "POST",
        f"/documents/{doc['id']}/revisions",
        {"revision": "1", "change_summary": "Synthetic first issue"},
        role="member",
        expected=201,
    )
    base = f"/documents/{doc['id']}/revisions/{revision['id']}"
    response = case.clients["member"].put(
        base + "/file", content=PDF, headers={"Content-Type": "application/pdf"}
    )
    assert response.status_code == 202, response.text
    assert response.json()["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert response.json()["file_state"] == "clean"
    revision = case.call("GET", f"/documents/{doc['id']}/revisions", role="member")[0]
    return doc, revision, storage


def release(case: Boundary, doc: dict[str, Any], revision: dict[str, Any]) -> dict[str, Any]:
    base = f"/documents/{doc['id']}/revisions/{revision['id']}"
    revision = case.call(
        "POST", base + "/submit", {"expected_version": revision["row_version"]}, role="member"
    )
    case.call(
        "POST",
        base + "/approve",
        {"expected_version": revision["row_version"]},
        role="member",
        expected=403,
    )
    revision = case.call(
        "POST", base + "/approve", {"expected_version": revision["row_version"]}, role="admin"
    )
    released: dict[str, Any] = case.call(
        "POST", base + "/release", {"expected_version": revision["row_version"]}, role="member"
    )
    return released


def test_document_http_combined_reviewer_reject_resubmit_approval_release_and_stale_command(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, storage = document(boundary, monkeypatch, combined_reviewer=True)
    base = f"/documents/{doc['id']}/revisions/{revision['id']}"
    revision = boundary.call(
        "POST", base + "/submit", {"expected_version": revision["row_version"]}, role="member"
    )
    revision = boundary.call(
        "POST", base + "/reject", {"expected_version": revision["row_version"]}, role="admin"
    )
    assert revision["status"] == "rejected"
    released = release(boundary, doc, revision)
    assert released["status"] == "active"
    assert released["approved_by_user_id"] == str(USERS["admin"])
    boundary.call("POST", base + "/release", {"expected_version": 1}, role="member", expected=409)
    response = boundary.clients["member"].get(base + "/file")
    assert response.status_code == 200 and response.content == PDF
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert list(storage.objects.values()) == [PDF]
    with boundary.admin.connect() as db:
        row = db.execute(
            text("SELECT status,current_revision_id FROM qms_documents WHERE id=:id"),
            {"id": doc["id"]},
        ).one()
        assert row.status == "active" and str(row.current_revision_id) == revision["id"]
        actions = list(
            db.scalars(
                text("SELECT action FROM audit_events WHERE resource_id=:id ORDER BY occurred_at"),
                {"id": revision["id"]},
            )
        )
        assert actions.count("revision.submitted") == 2
        assert actions.count("revision.rejected") == 1
        assert actions.count("revision.approved") == actions.count("revision.released") == 1


def test_document_http_failed_ledger_rolls_back_revision_command(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _storage = document(boundary, monkeypatch)

    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Synthetic ledger unavailable")

    monkeypatch.setattr(audit_service, "record_document", unavailable)
    client = boundary.clients["member"]
    with pytest.raises(RuntimeError, match="Synthetic ledger unavailable"):
        client.post(
            f"/documents/{doc['id']}/revisions/{revision['id']}/submit",
            json={"expected_version": revision["row_version"]},
        )
    with boundary.admin.connect() as db:
        row = db.execute(
            text("SELECT status,row_version FROM qms_document_revisions WHERE id=:id"),
            {"id": revision["id"]},
        ).one()
        assert tuple(row) == ("draft", revision["row_version"])
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id "
                    "AND action='revision.submitted'"
                ),
                {"id": revision["id"]},
            )
            == 0
        )


def test_action_center_http_sql_projects_all_existing_sources_and_review_authority(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _storage = document(boundary, monkeypatch, combined_reviewer=True)
    revision = release(boundary, doc, revision)
    grant(
        boundary,
        "member",
        "controls.read",
        "controls.manage",
        "control_instances.read",
        "control_instances.manage",
        "evidence.review",
        "capa.read",
        "capa.manage",
        "capa.review",
    )
    grant(
        boundary,
        "admin",
        "controls.read",
        "control_instances.read",
        "control_instances.manage",
        "evidence.review",
        "capa.read",
        "capa.review",
    )
    control = boundary.call(
        "POST",
        "/controls",
        {
            "unit_id": str(SITE),
            "process_id": boundary.process,
            "code": "HTTP-CONTROL",
            "name": "Synthetic control",
            "objective": "Evidence reviewed independently",
        },
        role="member",
        expected=201,
    )
    boundary.call(
        "POST",
        f"/controls/{control['id']}/activities",
        {"name": "Synthetic assigned activity"},
        role="member",
        expected=201,
    )
    boundary.call(
        "POST",
        f"/controls/{control['id']}/evidence-requirements",
        {"name": "Synthetic released procedure", "evidence_type": "document", "mandatory": True},
        role="member",
        expected=201,
    )
    control = boundary.call("GET", f"/controls/{control['id']}", role="member")
    boundary.call(
        "POST",
        f"/controls/{control['id']}/activate",
        {"expected_version": control["row_version"]},
        role="member",
    )
    instance = boundary.call(
        "POST",
        f"/control-instances?unit_id={SITE}&process_id={boundary.process}",
        {
            "control_id": control["id"],
            "code": "HTTP-IMPLEMENTATION",
            "name": "Synthetic implementation",
        },
        role="member",
        expected=201,
    )
    activity = boundary.call(
        "GET",
        f"/control-instance-activities?unit_id={SITE}&instance_id={instance['id']}",
        role="member",
    )[0]
    due = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    activity = boundary.call(
        "PATCH",
        f"/control-instance-activities/{activity['id']}",
        {
            "expected_version": activity["row_version"],
            "assigned_to_user_id": str(USERS["member"]),
            "target_date": due,
        },
        role="member",
    )
    evidence = boundary.call(
        "GET",
        f"/control-instance-evidence?unit_id={SITE}&instance_id={instance['id']}",
        role="member",
    )[0]
    evidence = boundary.call(
        "PATCH",
        f"/control-instance-evidence/{evidence['id']}",
        {
            "expected_version": evidence["row_version"],
            "document_id": doc["id"],
            "document_revision_id": revision["id"],
            "evidence_summary": "Synthetic released source",
        },
        role="member",
    )
    evidence = boundary.call(
        "POST",
        f"/control-instance-evidence/{evidence['id']}/submit",
        {"expected_version": evidence["row_version"]},
        role="member",
    )
    capa = boundary.call(
        "POST",
        "/capas",
        {
            "unit_id": str(SITE),
            "process_id": boundary.process,
            "code": "HTTP-CAPA",
            "name": "Synthetic corrective action",
            "source_type": "other",
            "problem_statement": "Synthetic owner assignment gap",
            "root_cause_method": "5why",
        },
        role="member",
        expected=201,
    )
    capa = boundary.call(
        "POST",
        f"/capas/{capa['id']}/analysis/start",
        {"expected_version": capa["row_version"]},
        role="member",
    )
    data = capa["analysis_data"]
    data["why1"] = "Synthetic missing ownership"
    capa = boundary.call(
        "PATCH",
        f"/capas/{capa['id']}/analysis",
        {
            "expected_version": capa["row_version"],
            "analysis_data": data,
            "analysis_summary": "Synthetic analysis",
            "verified_root_cause": "Synthetic missing ownership",
        },
        role="member",
    )
    capa = boundary.call(
        "POST",
        f"/capas/{capa['id']}/plan/start",
        {
            "expected_version": capa["row_version"],
            "plan_summary": "Assign and verify synthetic ownership",
        },
        role="member",
    )
    action = boundary.call(
        "POST",
        f"/capas/{capa['id']}/actions",
        {
            "expected_capa_version": capa["row_version"],
            "title": "Assign synthetic owner",
            "description": "Synthetic action",
            "owner_user_id": str(USERS["member"]),
            "due_date": due,
        },
        role="member",
        expected=201,
    )
    mine = boundary.call("GET", "/action-center?scope=mine", role="member")
    items = {item["source"]: item for item in mine["items"]}
    assert set(items) == {"workflow", "capa", "control_activity"}
    assert mine["summary"]["total"] == 3 and mine["summary"]["overdue"] == 2
    assert items["workflow"]["target_record_id"] == boundary.instance
    assert items["capa"]["target_subrecord_id"] == action["id"]
    assert items["control_activity"]["target_subrecord_id"] == activity["id"]
    assert items["control_activity"]["assignee_name"] == "Synthetic member"
    reviewed = boundary.call("GET", "/action-center?scope=mine", role="admin")
    assert {item["source"] for item in reviewed["items"]} == {"evidence_review"}
    assert reviewed["items"][0]["target_subrecord_id"] == evidence["id"]
    assert reviewed["items"][0]["target_process_id"] == boundary.process
    team = boundary.call("GET", "/action-center?scope=team", role="admin")
    assert {item["source"] for item in team["items"]} == {
        "workflow",
        "capa",
        "control_activity",
        "evidence_review",
    }
    boundary.call("GET", "/action-center?scope=team", role="member", expected=403)
    review_grant = next(
        row
        for row in boundary.call("GET", "/qms-access/grants")
        if row["user_id"] == str(USERS["admin"]) and row["capability"] == "evidence.review"
    )
    boundary.call("POST", f"/qms-access/grants/{review_grant['id']}/revoke")
    assert boundary.call("GET", "/action-center?scope=mine", role="admin")["items"] == []
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    assert boundary.call("GET", "/action-center?scope=team", role="owner")["items"] == []


class MinimalReviewerParentLockFailure(AssertionError):
    """Only the reproduced parent-row lock404 qualifies as the known defect."""


@pytest.mark.parametrize("action", ["reject", "approve"])
@pytest.mark.xfail(
    strict=True,
    raises=MinimalReviewerParentLockFailure,
    reason=(
        "M01: parent SELECT FOR UPDATE hides document for review/approve "
        "without author/release/obsolete"
    ),
)
def test_document_http_minimal_reviewer_can_decide_without_parent_write_grants(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    doc, revision, _storage = document(boundary, monkeypatch)
    base = f"/documents/{doc['id']}/revisions/{revision['id']}"
    revision = boundary.call(
        "POST", base + "/submit", {"expected_version": revision["row_version"]}, role="member"
    )
    effective = boundary.call("GET", f"/qms-access/effective?unit_id={SITE}", role="admin")
    assert set(effective["capabilities"]) == {
        "documents.read",
        "documents.review",
        "documents.approve",
    }
    visible = boundary.call("GET", f"/documents/{doc['id']}/revisions", role="admin")
    assert visible[0]["id"] == revision["id"] and visible[0]["status"] == "under_review"
    with boundary.runtime.begin() as db:
        context(db, user=USERS["admin"])
        assert db.scalar(text("SELECT id FROM qms_documents WHERE id=:id"), {"id": doc["id"]})
        assert (
            db.scalar(
                text("SELECT id FROM qms_documents WHERE id=:id FOR UPDATE"), {"id": doc["id"]}
            )
            is None
        )
    response = boundary.clients["admin"].post(
        base + "/" + action, json={"expected_version": revision["row_version"]}
    )
    if response.status_code == 404 and response.json() == {"detail": "document not found"}:
        with boundary.admin.connect() as db:
            row = db.execute(
                text("SELECT status,row_version FROM qms_document_revisions WHERE id=:id"),
                {"id": revision["id"]},
            ).one()
            assert tuple(row) == ("under_review", revision["row_version"])
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action=:action"
                    ),
                    {
                        "id": revision["id"],
                        "action": "revision." + ("rejected" if action == "reject" else "approved"),
                    },
                )
                == 0
            )
        raise MinimalReviewerParentLockFailure(
            f"M01: {action} returned404 document not found despite read/review/approve; "
            "parent FOR UPDATE invisible"
        )
    assert response.status_code == 200, response.text
