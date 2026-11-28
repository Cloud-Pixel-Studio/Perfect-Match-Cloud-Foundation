from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from test_module_operability_http_integrity import PDF, document, release
from test_tenant_suspension_integrity import USERS, A, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service, documents
from pmc_api.antivirus import ScanVerdict

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]
PATH = f"/company-storage/{A}"


def _file_path(boundary: Boundary, doc_id: str, revision_code: str) -> str:
    revision = boundary.call(
        "POST",
        f"/documents/{doc_id}/revisions",
        {"revision": revision_code, "change_summary": "Synthetic storage fixture"},
        role="member",
        expected=201,
    )
    return f"/documents/{doc_id}/revisions/{revision['id']}/file"


def test_aggregate_counts_retained_revisions_and_excludes_rejected_files(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert boundary.call("GET", PATH)["document_file_count"] == 0
    doc, first, _storage = document(boundary, monkeypatch, combined_reviewer=True)
    release(boundary, doc, first)
    member = boundary.clients["member"]
    second_content = PDF + b"\n% Second edition."
    response = member.put(
        _file_path(boundary, doc["id"], "2"),
        content=second_content,
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 202 and response.json()["file_state"] == "clean"
    second = boundary.call("GET", f"/documents/{doc['id']}/revisions", role="member")
    latest = next(row for row in second if row["revision"] == "2")
    release(boundary, doc, latest)
    stored = boundary.call("GET", f"/documents/{doc['id']}/revisions", role="member")
    assert next(row for row in stored if row["revision"] == "1")["status"] == "superseded"

    monkeypatch.setattr(documents, "scan", lambda _payload: ScanVerdict.INFECTED)
    rejected = member.put(
        _file_path(boundary, doc["id"], "3"),
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    )
    assert rejected.status_code == 202 and rejected.json()["file_state"] == "rejected"
    assert boundary.call("GET", PATH, role="admin") == {
        "tenant_id": str(A),
        "recorded_bytes": len(PDF) + len(second_content),
        "document_file_count": 2,
    }


def test_aggregate_respects_session_and_company_boundaries_without_granting_document_access(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    document(boundary, monkeypatch)
    response = boundary.clients["owner"].get(PATH)
    assert response.status_code == 200 and response.json()["recorded_bytes"] == len(PDF)
    assert response.headers["x-tenant-id"] == str(A)
    assert response.headers["cache-control"] == "private, no-store"
    for role in ("member", "auditor"):
        boundary.call("GET", PATH, role=role, expected=403)
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM qms_document_revisions")) == 0
        assert not db.scalar(
            text("SELECT has_table_privilege(current_user, 'company_document_storage', 'UPDATE')")
        )
    with boundary.runtime.begin() as db:
        context(db, user=USERS["member"], tenant=A)
        assert db.scalar(text("SELECT count(*) FROM company_document_storage")) == 0
    boundary.call("GET", f"/company-storage/{B}", expected=409)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    assert boundary.call("GET", f"/company-storage/{B}")["recorded_bytes"] == 0
    boundary.call("GET", PATH, expected=409)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(A)})
    boundary.change("tenant", False)
    boundary.call("GET", PATH, expected=403)


def test_storage_totals_follow_upload_transactions_under_concurrency_and_rollback(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _, storage = document(boundary, monkeypatch)
    paths = [_file_path(boundary, doc["id"], code) for code in ("2", "3", "4")]
    member = boundary.clients["member"]
    headers = {"Content-Type": "application/pdf"}

    def put(path: str) -> int:
        return int(member.put(path, content=PDF, headers=headers).status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(put, paths[:2])) == [202, 202]
    assert boundary.call("GET", PATH)["recorded_bytes"] == 3 * len(PDF)
    assert boundary.call("GET", PATH)["document_file_count"] == 3

    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Synthetic upload audit failure")

    monkeypatch.setattr(audit_service, "record_document", unavailable)
    with pytest.raises(RuntimeError, match="Synthetic upload audit failure"):
        put(paths[2])
    assert boundary.call("GET", PATH)["recorded_bytes"] == 3 * len(PDF)
    assert boundary.call("GET", PATH)["document_file_count"] == 3
    assert len(storage.objects) == 3
