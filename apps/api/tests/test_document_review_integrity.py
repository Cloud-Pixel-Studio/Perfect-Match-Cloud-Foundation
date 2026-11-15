# ruff: noqa: E501
"""Document command authority and locking against disposable SQL only.

AV and object storage use memory. Sessions, CSRF, HTTP, RLS and ledger are real.
The shared fixture intentionally requires the pmcloud_tenant_suspension test DB.
"""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any, BinaryIO
from uuid import UUID

import pytest
from sqlalchemy import event, text
from test_tenant_suspension_integrity import SITE, USERS, A, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service, documents
from pmc_api.antivirus import ScanVerdict

pytestmark = [
    pytest.mark.document_review_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires the dedicated disposable document command harness",
    ),
]
PDF = b"%PDF-1.7\nSynthetic document command fixture.\n%%EOF\n"


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
    case: Boundary, monkeypatch: pytest.MonkeyPatch
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


def path(doc: dict[str, Any], revision: dict[str, Any], action: str) -> str:
    return f"/documents/{doc['id']}/revisions/{revision['id']}/{action}"


def prepare_review(
    case: Boundary, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], MemoryStorage]:
    doc, revision, storage = document(case, monkeypatch)
    revision = case.call(
        "POST",
        path(doc, revision, "submit"),
        {"expected_version": revision["row_version"]},
        role="member",
    )
    return doc, revision, storage


def set_reviewer_profile(case: Boundary, capabilities: set[str]) -> None:
    for row in case.call("GET", "/qms-access/grants"):
        if (
            row["user_id"] == str(USERS["admin"])
            and row["status"] == "active"
            and row["capability"] not in capabilities
        ):
            case.call("POST", f"/qms-access/grants/{row['id']}/revoke")
    current = case.call("GET", f"/qms-access/effective?unit_id={SITE}", role="admin")
    assert set(current["capabilities"]) == capabilities


@pytest.mark.parametrize(
    ("action", "capability", "status"),
    [("reject", "documents.review", "rejected"), ("approve", "documents.approve", "approved")],
)
def test_minimal_reviewer_can_decide_without_parent_write_authority(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, action: str, capability: str, status: str
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    set_reviewer_profile(boundary, {capability})
    with boundary.runtime.begin() as db:
        context(db, user=USERS["admin"])
        assert db.scalar(text("SELECT id FROM qms_documents WHERE id=:id"), {"id": doc["id"]})
        assert (
            db.scalar(
                text("SELECT id FROM qms_documents WHERE id=:id FOR UPDATE"), {"id": doc["id"]}
            )
            is None
        )
    result = boundary.call(
        "POST",
        path(doc, revision, action),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    assert result["status"] == status and result["row_version"] == revision["row_version"] + 1
    with boundary.admin.connect() as db:
        parent = db.execute(
            text("SELECT row_version,status,current_revision_id FROM qms_documents WHERE id=:id"),
            {"id": doc["id"]},
        ).one()
        assert tuple(parent) == (doc["row_version"], "draft", None)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action=:action AND actor_user_id=:actor"
                ),
                {"id": revision["id"], "action": "revision." + status, "actor": USERS["admin"]},
            )
            == 1
        )
    boundary.call(
        "POST",
        path(doc, result, "release"),
        {"expected_version": result["row_version"]},
        role="admin",
        expected=404,
    )


def test_review_succeeds_while_a_parent_writer_holds_its_row_lock(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    set_reviewer_profile(boundary, {"documents.approve"})
    with ThreadPoolExecutor(max_workers=1) as pool, boundary.runtime.begin() as holder:
        context(holder, user=USERS["member"])
        assert holder.scalar(
            text("SELECT id FROM qms_documents WHERE id=:id FOR UPDATE"), {"id": doc["id"]}
        )
        future = pool.submit(
            boundary.clients["admin"].post,
            path(doc, revision, "approve"),
            json={"expected_version": revision["row_version"]},
        )
        response = future.result(timeout=5)
        assert response.status_code == 200, response.text


def approved(
    case: Boundary, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], MemoryStorage]:
    doc, revision, storage = prepare_review(case, monkeypatch)
    revision = case.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    return doc, revision, storage


def test_release_waits_for_parent_without_locking_a_child_first(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Combined authority is explicit only to seed an approved revision on old code.
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    grant(boundary, "admin", "documents.release")
    revision = boundary.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    waiting = Event()

    def observe(
        _connection: Any, _cursor: Any, statement: str, _parameters: Any, _context: Any, _many: Any
    ) -> None:
        if "FROM qms_documents" in statement and "FOR UPDATE" in statement:
            waiting.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with boundary.runtime.begin() as holder:
            context(holder, user=USERS["member"])
            assert holder.scalar(
                text("SELECT id FROM qms_documents WHERE id=:id FOR UPDATE"), {"id": doc["id"]}
            )
            event.listen(boundary.runtime, "before_cursor_execute", observe)
            try:
                future = pool.submit(
                    boundary.clients["member"].post,
                    path(doc, revision, "release"),
                    json={"expected_version": revision["row_version"]},
                )
                assert waiting.wait(timeout=5), "release must reach the held document"
                with boundary.runtime.begin() as probe:
                    context(probe, user=USERS["member"])
                    assert probe.scalar(
                        text(
                            "SELECT id FROM qms_document_revisions WHERE id=:id FOR UPDATE NOWAIT"
                        ),
                        {"id": revision["id"]},
                    )
            finally:
                event.remove(boundary.runtime, "before_cursor_execute", observe)
        response = future.result(timeout=5)
    assert response.status_code == 200, response.text


def snapshot(case: Boundary, revision_id: str) -> tuple[str, int, int]:
    with case.admin.connect() as db:
        row = db.execute(
            text("SELECT status,row_version FROM qms_document_revisions WHERE id=:id"),
            {"id": revision_id},
        ).one()
        events = db.scalar(
            text(
                "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action IN ('revision.approved','revision.rejected','revision.released')"
            ),
            {"id": revision_id},
        )
    return str(row[0]), int(row[1]), int(events or 0)


def test_minimal_review_can_submit_reject_resubmit_then_independent_approval_and_release(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = document(boundary, monkeypatch)
    set_reviewer_profile(boundary, {"documents.review"})
    revision = boundary.call(
        "POST",
        path(doc, revision, "submit"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    revision = boundary.call(
        "POST",
        path(doc, revision, "reject"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    revision = boundary.call(
        "POST",
        path(doc, revision, "submit"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    boundary.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"]},
        role="member",
        expected=403,
    )
    grant(boundary, "admin", "documents.approve")
    revision = boundary.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    result = boundary.call(
        "POST",
        path(doc, revision, "release"),
        {"expected_version": revision["row_version"]},
        role="member",
    )
    assert result["status"] == "active"
    with boundary.admin.connect() as db:
        parent = db.execute(
            text("SELECT status,current_revision_id,row_version FROM qms_documents WHERE id=:id"),
            {"id": doc["id"]},
        ).one()
        assert tuple(parent) == ("active", UUID(result["id"]), doc["row_version"] + 1)


@pytest.mark.parametrize("action", ["approve", "reject", "submit", "release"])
def test_read_only_member_cannot_decide_or_release(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    set_reviewer_profile(boundary, {"documents.read"})
    before = snapshot(boundary, revision["id"])
    boundary.call(
        "POST",
        path(doc, revision, action),
        {"expected_version": revision["row_version"]},
        role="admin",
        expected=404,
    )
    assert snapshot(boundary, revision["id"]) == before


def test_minimal_review_does_not_gain_parent_update_authority(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    with boundary.runtime.begin() as db:
        context(db, user=USERS["admin"])
        result = db.execute(
            text(
                "UPDATE qms_documents SET title='Forbidden',row_version=row_version+1 WHERE id=:id RETURNING id"
            ),
            {"id": doc["id"]},
        ).first()
        assert result is None
    boundary.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"]},
        role="admin",
    )
    with boundary.admin.connect() as db:
        assert (
            db.scalar(text("SELECT title FROM qms_documents WHERE id=:id"), {"id": doc["id"]})
            == doc["title"]
        )


def test_stale_command_and_missing_csrf_do_not_change_revision(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    before = snapshot(boundary, revision["id"])
    boundary.call(
        "POST",
        path(doc, revision, "approve"),
        {"expected_version": revision["row_version"] - 1},
        role="admin",
        expected=409,
    )
    client = boundary.clients["admin"]
    csrf = client.headers.pop("X-CSRF-Token")
    try:
        missing = client.post(
            path(doc, revision, "approve"),
            json={"expected_version": revision["row_version"]},
        )
        assert missing.status_code == 403
    finally:
        client.headers["X-CSRF-Token"] = csrf
    response = boundary.clients["admin"].post(
        path(doc, revision, "approve"),
        json={"expected_version": revision["row_version"]},
        headers={"X-CSRF-Token": "synthetic-wrong"},
    )
    assert response.status_code == 403
    assert snapshot(boundary, revision["id"]) == before


def test_ledger_failure_rolls_back_minimal_reviewer_decision(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    before = snapshot(boundary, revision["id"])

    def unavailable(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("synthetic ledger unavailable")

    monkeypatch.setattr(audit_service, "record_document", unavailable)
    with pytest.raises(RuntimeError, match="synthetic ledger unavailable"):
        boundary.clients["admin"].post(
            path(doc, revision, "approve"), json={"expected_version": revision["row_version"]}
        )
    assert snapshot(boundary, revision["id"]) == before


def test_parallel_approve_and_reject_have_one_winner_and_one_conflict(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    gate = Barrier(2)

    def decide(action: str) -> Any:
        gate.wait(timeout=5)
        return boundary.clients["admin"].post(
            path(doc, revision, action), json={"expected_version": revision["row_version"]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(decide, action) for action in ("approve", "reject")]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in results) == [200, 409]
    state, version, events = snapshot(boundary, revision["id"])
    assert (
        state in {"approved", "rejected"} and version == revision["row_version"] + 1 and events == 1
    )


def test_revoked_approval_while_waiting_for_revision_lock_fails_closed(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    before = snapshot(boundary, revision["id"])
    waiting = Event()

    def observe(
        _connection: Any, _cursor: Any, statement: str, _parameters: Any, _context: Any, _many: Any
    ) -> None:
        if "FROM qms_document_revisions" in statement and "FOR UPDATE" in statement:
            waiting.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with boundary.runtime.begin() as holder:
            context(holder, user=USERS["member"])
            assert holder.scalar(
                text("SELECT id FROM qms_document_revisions WHERE id=:id FOR UPDATE"),
                {"id": revision["id"]},
            )
            event.listen(boundary.runtime, "before_cursor_execute", observe)
            try:
                future = pool.submit(
                    boundary.clients["admin"].post,
                    path(doc, revision, "approve"),
                    json={"expected_version": revision["row_version"]},
                )
                assert waiting.wait(timeout=5)
                grant_id = next(
                    row["id"]
                    for row in boundary.call("GET", "/qms-access/grants")
                    if row["user_id"] == str(USERS["admin"])
                    and row["capability"] == "documents.approve"
                    and row["status"] == "active"
                )
                boundary.call("POST", f"/qms-access/grants/{grant_id}/revoke")
            finally:
                event.remove(boundary.runtime, "before_cursor_execute", observe)
        response = future.result(timeout=5)
    assert response.status_code == 403, response.text
    assert snapshot(boundary, revision["id"]) == before


def test_changing_company_does_not_carry_document_authority(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, revision, _ = prepare_review(boundary, monkeypatch)
    before = snapshot(boundary, revision["id"])
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    for action in ("submit", "reject", "approve", "release"):
        boundary.call(
            "POST",
            path(doc, revision, action),
            {"expected_version": revision["row_version"]},
            expected=404,
        )
    with boundary.runtime.begin() as db:
        context(db, user=USERS["owner"], tenant=B)
        assert (
            db.scalar(text("SELECT id FROM qms_documents WHERE id=:id"), {"id": doc["id"]}) is None
        )
        assert (
            db.scalar(
                text("SELECT id FROM qms_document_revisions WHERE id=:id"), {"id": revision["id"]}
            )
            is None
        )
    assert snapshot(boundary, revision["id"]) == before


def test_parallel_releases_preserve_one_active_revision_and_current_pointer(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, initial, _ = approved(boundary, monkeypatch)
    initial = boundary.call(
        "POST",
        path(doc, initial, "release"),
        {"expected_version": initial["row_version"]},
        role="member",
    )
    next_revisions = []
    for label in ("2", "3"):
        revision = boundary.call(
            "POST",
            f"/documents/{doc['id']}/revisions",
            {"revision": label, "change_summary": "Synthetic replacement"},
            role="member",
            expected=201,
        )
        response = boundary.clients["member"].put(
            path(doc, revision, "file"), content=PDF, headers={"Content-Type": "application/pdf"}
        )
        assert response.status_code == 202
        revision = next(
            row
            for row in boundary.call("GET", f"/documents/{doc['id']}/revisions", role="member")
            if row["id"] == revision["id"]
        )
        revision = boundary.call(
            "POST",
            path(doc, revision, "submit"),
            {"expected_version": revision["row_version"]},
            role="member",
        )
        revision = boundary.call(
            "POST",
            path(doc, revision, "approve"),
            {"expected_version": revision["row_version"]},
            role="admin",
        )
        next_revisions.append(revision)
    gate = Barrier(2)

    def release_one(revision: dict[str, Any]) -> Any:
        gate.wait(timeout=5)
        return boundary.clients["member"].post(
            path(doc, revision, "release"), json={"expected_version": revision["row_version"]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(release_one, revision) for revision in next_revisions]
        results = [future.result(timeout=10) for future in futures]
    assert [response.status_code for response in results] == [200, 200]
    with boundary.admin.connect() as db:
        rows = db.execute(
            text("SELECT id,status FROM qms_document_revisions WHERE document_id=:id"),
            {"id": doc["id"]},
        ).all()
        active = [str(row.id) for row in rows if row.status == "active"]
        assert len(active) == 1 and sum(row.status == "superseded" for row in rows) == 2
        parent = db.execute(
            text("SELECT current_revision_id,row_version FROM qms_documents WHERE id=:id"),
            {"id": doc["id"]},
        ).one()
        assert (
            str(parent.current_revision_id) == active[0]
            and parent.row_version == doc["row_version"] + 3
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE tenant_id=:tenant AND resource_id IN (SELECT id FROM qms_document_revisions WHERE document_id=:doc) AND action='revision.released'"
                ),
                {"tenant": A, "doc": doc["id"]},
            )
            == 3
        )


@pytest.mark.parametrize("ledger_failure", [False, True])
def test_ordered_switch_retires_previous_before_lower_uuid_and_rolls_back_atomically(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, ledger_failure: bool
) -> None:
    identifiers = iter(
        UUID(value)
        for value in [
            "b1000000-0000-4000-8000-000000000001",
            "f1000000-0000-4000-8000-000000000001",
            "b2000000-0000-4000-8000-000000000001",
            "01000000-0000-4000-8000-000000000001",
            "b2000000-0000-4000-8000-000000000002",
        ]
    )
    monkeypatch.setattr(documents, "uuid4", lambda: next(identifiers))
    doc, previous, _ = approved(boundary, monkeypatch)
    previous = boundary.call(
        "POST",
        path(doc, previous, "release"),
        {"expected_version": previous["row_version"]},
        role="member",
    )
    target = boundary.call(
        "POST", f"/documents/{doc['id']}/revisions", {"revision": "2"}, role="member", expected=201
    )
    assert UUID(target["id"]) < UUID(previous["id"])
    response = boundary.clients["member"].put(
        path(doc, target, "file"), content=PDF, headers={"Content-Type": "application/pdf"}
    )
    assert response.status_code == 202
    target = next(
        row
        for row in boundary.call("GET", f"/documents/{doc['id']}/revisions", role="member")
        if row["id"] == target["id"]
    )
    target = boundary.call(
        "POST",
        path(doc, target, "submit"),
        {"expected_version": target["row_version"]},
        role="member",
    )
    target = boundary.call(
        "POST",
        path(doc, target, "approve"),
        {"expected_version": target["row_version"]},
        role="admin",
    )
    old_previous, old_target = snapshot(boundary, previous["id"]), snapshot(boundary, target["id"])
    if ledger_failure:

        def unavailable(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("synthetic replacement ledger unavailable")

        monkeypatch.setattr(audit_service, "record_document", unavailable)
        with pytest.raises(RuntimeError, match="synthetic replacement ledger unavailable"):
            boundary.clients["member"].post(
                path(doc, target, "release"), json={"expected_version": target["row_version"]}
            )
        assert snapshot(boundary, previous["id"]) == old_previous
        assert snapshot(boundary, target["id"]) == old_target
        expected_current, expected_version = previous["id"], doc["row_version"] + 1
    else:
        result = boundary.call(
            "POST",
            path(doc, target, "release"),
            {"expected_version": target["row_version"]},
            role="member",
        )
        assert result["status"] == "active"
        assert snapshot(boundary, previous["id"]) == (
            "superseded",
            old_previous[1] + 1,
            old_previous[2],
        )
        assert snapshot(boundary, target["id"]) == ("active", old_target[1] + 1, old_target[2] + 1)
        expected_current, expected_version = target["id"], doc["row_version"] + 2
    with boundary.admin.connect() as db:
        parent = db.execute(
            text("SELECT current_revision_id,row_version FROM qms_documents WHERE id=:id"),
            {"id": doc["id"]},
        ).one()
        assert (
            str(parent.current_revision_id) == expected_current
            and parent.row_version == expected_version
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM qms_document_revisions WHERE document_id=:id AND status='active'"
                ),
                {"id": doc["id"]},
            )
            == 1
        )
