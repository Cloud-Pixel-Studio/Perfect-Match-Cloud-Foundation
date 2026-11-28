from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.exc import DBAPIError
from test_employee_directory_integrity import synthetic_portrait
from test_module_operability_http_integrity import PDF, document, release
from test_tenant_suspension_integrity import SITE, USERS, A, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service, documents, employee_portraits
from pmc_api.antivirus import ScanVerdict
from pmc_api.document_storage_reconciliation import InventoryError, load_references

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]
PATH = f"/company-storage/{A}"


@pytest.fixture
def operations() -> Iterator[Engine]:
    engine = create_engine(os.environ["PMC_DATABASE_URL"])
    try:
        yield engine
    finally:
        engine.dispose()


def _approve(operations: Engine, tenant: UUID, allowance: int, version: int, approval: UUID) -> int:
    with operations.begin() as db:
        result = db.scalar(
            text("SELECT public.record_company_storage_allowance(:tenant, :bytes, :version, :id)"),
            {"tenant": tenant, "bytes": allowance, "version": version, "id": approval},
        )
        assert isinstance(result, int)
        return result


def _file_path(boundary: Boundary, doc_id: str, revision_code: str) -> str:
    revision = boundary.call(
        "POST",
        f"/documents/{doc_id}/revisions",
        {"revision": revision_code, "change_summary": "Synthetic storage fixture"},
        role="member",
        expected=201,
    )
    return f"/documents/{doc_id}/revisions/{revision['id']}/file"


def test_employee_photos_and_pdfs_share_the_same_allowance(
    boundary: Boundary, operations: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _revision, _storage = document(boundary, monkeypatch)
    profile = boundary.call(
        "POST",
        f"/employees/{A}",
        {
            "full_name": "Synthetic Employee",
            "job_title": "Inspector",
            "unit_id": str(SITE),
        },
        expected=201,
    )
    photo = f"/employees/{A}/{profile['id']}/photo"
    payload = synthetic_portrait()
    photo_size = len(employee_portraits._normalize(payload, "PNG"))
    owner = boundary.clients["owner"]
    assert photo_size > len(PDF)
    monkeypatch.setattr(employee_portraits, "scan", lambda _: ScanVerdict.CLEAN)
    _approve(operations, A, len(PDF) + photo_size - 1, 0, uuid4())
    assert (
        owner.put(
            photo + "?expected_version=1", content=payload, headers={"Content-Type": "image/png"}
        ).status_code
        == 507
    )
    assert owner.get(photo).status_code == 404
    assert boundary.call("GET", PATH)["recorded_bytes"] == len(PDF)

    _approve(operations, A, len(PDF) + photo_size, 1, uuid4())
    assert (
        owner.put(
            photo + "?expected_version=1", content=payload, headers={"Content-Type": "image/png"}
        ).status_code
        == 200
    )
    usage = boundary.call("GET", PATH)
    assert usage["recorded_bytes"] == len(PDF) + photo_size
    assert usage["employee_photo_count"] == 1 and usage["employee_photo_bytes"] == photo_size
    assert usage["usage_status"] == "at_limit"
    member = boundary.clients["member"]
    second = _file_path(boundary, doc["id"], "2")
    assert (
        member.put(second, content=PDF, headers={"Content-Type": "application/pdf"}).status_code
        == 507
    )
    assert owner.delete(photo + "?expected_version=2").status_code == 200
    assert (
        member.put(second, content=PDF, headers={"Content-Type": "application/pdf"}).status_code
        == 202
    )
    usage = boundary.call("GET", PATH)
    assert usage["recorded_bytes"] == 2 * len(PDF)
    assert (usage["employee_photo_count"], usage["employee_photo_bytes"]) == (0, 0)


def test_two_employee_photos_cannot_spend_the_same_capacity(
    boundary: Boundary, operations: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = f"/employees/{A}"
    profiles = [
        boundary.call(
            "POST",
            directory,
            {"full_name": f"Synthetic {role}", "job_title": "Inspector", "unit_id": str(SITE)},
            role=role,
            expected=201,
        )
        for role in ("owner", "admin")
    ]
    payload = synthetic_portrait()
    photo_size = len(employee_portraits._normalize(payload, "PNG"))
    _approve(operations, A, photo_size, 0, uuid4())
    ready = Barrier(2, timeout=5)

    def scan_together(_payload: object) -> ScanVerdict:
        ready.wait()
        return ScanVerdict.CLEAN

    monkeypatch.setattr(employee_portraits, "scan", scan_together)

    def upload(role: str, profile_id: str) -> int:
        response = boundary.clients[role].put(
            f"{directory}/{profile_id}/photo?expected_version=1",
            content=payload,
            headers={"Content-Type": "image/png"},
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(upload, "owner", profiles[0]["id"])
        admin = executor.submit(upload, "admin", profiles[1]["id"])
        assert sorted([owner.result(timeout=10), admin.result(timeout=10)]) == [200, 507]
    usage = boundary.call("GET", PATH)
    assert (usage["recorded_bytes"], usage["employee_photo_count"]) == (photo_size, 1)
    assert (
        sum(employee["has_portrait"] for employee in boundary.call("GET", directory)["items"]) == 1
    )


def test_document_inventory_requires_dedicated_role_and_scopes_references(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, revision, stored = document(boundary, monkeypatch)
    ((_, key),) = stored.objects
    with pytest.raises(DBAPIError):
        load_references(boundary.runtime, A)
    with pytest.raises(InventoryError, match="dedicated"):
        load_references(boundary.admin, A)

    with boundary.admin.begin() as db:
        db.execute(text("CREATE ROLE pmcloud_test_document_inventory NOLOGIN BYPASSRLS"))
        db.execute(text("GRANT SELECT (id) ON tenants TO pmcloud_test_document_inventory"))
        db.execute(
            text("""
                GRANT SELECT (id, tenant_id, file_object_key, file_size)
                ON qms_document_revisions TO pmcloud_test_document_inventory
            """)
        )
    engine = create_engine(boundary.admin.url)

    @event.listens_for(engine, "begin")
    def select_inventory_role(db: Connection) -> None:
        db.exec_driver_sql("SET LOCAL ROLE pmcloud_test_document_inventory")

    try:
        references = load_references(engine, A)
        assert [(ref.revision_id, ref.key, ref.size) for ref in references] == [
            (UUID(revision["id"]), key, len(PDF))
        ]
        assert load_references(engine, B) == []
        with pytest.raises(InventoryError, match="does not exist"):
            load_references(engine, uuid4())
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(text("SELECT title FROM qms_documents"))
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(text("UPDATE qms_document_revisions SET file_size = 0"))
    finally:
        engine.dispose()
        with boundary.admin.begin() as db:
            db.execute(text("REVOKE ALL ON tenants FROM pmcloud_test_document_inventory"))
            db.execute(
                text("REVOKE ALL ON qms_document_revisions FROM pmcloud_test_document_inventory")
            )
            db.execute(text("DROP ROLE pmcloud_test_document_inventory"))


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
        "employee_photo_bytes": 0,
        "employee_photo_count": 0,
        "allowance_bytes": None,
        "available_bytes": None,
        "usage_percent": None,
        "usage_status": "unconfigured",
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


def test_approved_allowances_are_versioned_and_tenant_read_only(
    boundary: Boundary, operations: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    document(boundary, monkeypatch)
    initial = uuid4()
    assert _approve(operations, A, len(PDF), 0, initial) == 1
    assert _approve(operations, A, len(PDF), 0, initial) == 1
    with pytest.raises(DBAPIError, match="storage approval already used"):
        _approve(operations, A, 10_000_000, 0, initial)
    usage = boundary.call("GET", PATH)
    assert (usage["allowance_bytes"], usage["available_bytes"], usage["usage_status"]) == (
        len(PDF),
        0,
        "at_limit",
    )
    with pytest.raises(DBAPIError, match="storage allowance version changed"):
        _approve(operations, A, 1, 0, uuid4())
    assert _approve(operations, A, len(PDF) - 1, 1, uuid4()) == 2
    assert _approve(operations, B, 25_000_000, 0, uuid4()) == 1

    usage = boundary.call("GET", PATH, role="admin")
    assert (usage["recorded_bytes"], usage["available_bytes"], usage["usage_status"]) == (
        len(PDF),
        0,
        "over_limit",
    )
    assert "approval_id" not in usage and "recorded_by" not in usage
    with boundary.admin.connect() as db:
        rows = db.execute(
            text(
                "SELECT row_version, recorded_by FROM public.company_storage_allowances "
                "WHERE tenant_id=:tenant ORDER BY row_version"
            ),
            {"tenant": A},
        ).all()
        assert [(row.row_version, row.recorded_by) for row in rows] == [
            (1, "pmcloud_migrator"),
            (2, "pmcloud_migrator"),
        ]
    with (
        pytest.raises(DBAPIError, match="storage allowance history is append-only"),
        operations.begin() as db,
    ):
        db.execute(text("UPDATE public.company_storage_allowances SET allowance_bytes=1"))
    with boundary.runtime.begin() as db:
        context(db)
        assert not db.scalar(
            text(
                "SELECT has_function_privilege(current_user, "
                "'public.record_company_storage_allowance(uuid,bigint,integer,uuid)', 'EXECUTE')"
            )
        )
        assert not db.scalar(
            text(
                "SELECT has_column_privilege(current_user, 'company_storage_allowances', "
                "'approval_id', 'SELECT')"
            )
        )
        assert (
            db.scalar(text("SELECT count(allowance_bytes) FROM public.company_storage_allowances"))
            == 2
        )
    with boundary.runtime.begin() as db:
        context(db, user=USERS["member"], tenant=A)
        assert (
            db.scalar(text("SELECT count(allowance_bytes) FROM public.company_storage_allowances"))
            == 0
        )
    boundary.call("GET", PATH, role="member", expected=403)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    assert boundary.call("GET", f"/company-storage/{B}")["available_bytes"] == 25_000_000
    boundary.call("GET", PATH, expected=409)


def test_concurrent_approvals_for_one_version_cannot_both_commit(
    boundary: Boundary, operations: Engine
) -> None:
    def approve(amount: int) -> int:
        try:
            return _approve(operations, A, amount, 0, uuid4())
        except DBAPIError as exc:
            assert "storage allowance version changed" in str(exc)
            return 0

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(approve, (5_000_000, 6_000_000))) == [0, 1]
    assert boundary.call("GET", PATH)["allowance_bytes"] in {5_000_000, 6_000_000}


def test_concurrent_pdf_uploads_stop_at_exact_quota_and_preserve_existing_content(
    boundary: Boundary, operations: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, first, storage = document(boundary, monkeypatch, combined_reviewer=True)
    release(boundary, doc, first)
    assert _approve(operations, A, 2 * len(PDF), 0, uuid4()) == 1
    paths = [_file_path(boundary, doc["id"], code) for code in ("2", "3")]
    member = boundary.clients["member"]

    def upload(path: str) -> int:
        return int(
            member.put(path, content=PDF, headers={"Content-Type": "application/pdf"}).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(upload, paths)) == [202, 507]
    usage = boundary.call("GET", PATH)
    assert (usage["recorded_bytes"], usage["usage_status"], usage["document_file_count"]) == (
        2 * len(PDF),
        "at_limit",
        2,
    )
    assert len(storage.objects) == 2
    revisions = boundary.call("GET", f"/documents/{doc['id']}/revisions", role="member")
    pending = next(item for item in revisions if item["file_state"] == "missing")
    assert pending["row_version"] == 1
    assert _approve(operations, A, len(PDF) - 1, 1, uuid4()) == 2
    assert upload(f"/documents/{doc['id']}/revisions/{pending['id']}/file") == 507
    response = member.get(f"/documents/{doc['id']}/revisions/{first['id']}/file")
    assert response.status_code == 200 and response.content == PDF
    assert len(storage.objects) == 2


def test_batched_document_records_cannot_exceed_company_allowance(
    boundary: Boundary, operations: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _, storage = document(boundary, monkeypatch)
    for code in ("2", "3"):
        _file_path(boundary, doc["id"], code)
    assert _approve(operations, A, 2 * len(PDF), 0, uuid4()) == 1
    with boundary.runtime.begin() as db:
        context(db, user=USERS["member"], tenant=A)
        with (
            pytest.raises(DBAPIError, match="company document storage allowance exceeded"),
            db.begin_nested(),
        ):
            db.execute(
                text(
                    "UPDATE public.qms_document_revisions "
                    "SET file_state='clean', file_object_key=id::text, file_sha256=repeat('a',64), "
                    "file_size=:size, file_media_type='application/pdf', row_version=row_version+1 "
                    "WHERE document_id=:document AND file_state='missing'"
                ),
                {"document": doc["id"], "size": len(PDF)},
            )
    usage = boundary.call("GET", PATH)
    assert usage["recorded_bytes"] == len(PDF) and usage["document_file_count"] == 1
    assert len(storage.objects) == 1
