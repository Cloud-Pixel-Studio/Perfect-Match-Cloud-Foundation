from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from pmc_api import documents
from pmc_api.antivirus import ScanUnavailable, ScanVerdict
from pmc_api.auth import AuthenticatedSession
from pmc_api.organization_service import OrganizationActor


def _inputs(
    monkeypatch: pytest.MonkeyPatch, *, file_state: str
) -> tuple[tuple[UUID, UUID], tuple[SimpleNamespace, SimpleNamespace]]:
    tenant_id, user_id, unit_id = uuid4(), uuid4(), uuid4()
    document_id, revision_id = uuid4(), uuid4()
    revision = SimpleNamespace(
        id=revision_id,
        document_id=document_id,
        tenant_id=tenant_id,
        file_state=file_state,
        file_object_key="private/object-key",
        file_sha256=hashlib.sha256(b"%PDF-test").hexdigest(),
        file_size=len(b"%PDF-test"),
    )
    document = SimpleNamespace(id=document_id, tenant_id=tenant_id, unit_id=unit_id)
    actor = OrganizationActor(user_id, "Tester", "member", tenant_id)
    monkeypatch.setattr(documents, "actor_context", lambda _db, _auth: actor)
    monkeypatch.setattr(documents, "require_capability", lambda *_args: None)
    rows = iter((revision, document))
    db = SimpleNamespace(scalar=lambda *_args: next(rows))
    return (document_id, revision_id), (db, revision)


def test_quarantined_revision_cannot_be_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    identifiers, resources = _inputs(monkeypatch, file_state="quarantined")
    db, _revision = resources
    storage = SimpleNamespace(get_object=lambda *_args: pytest.fail("storage must not be read"))
    monkeypatch.setattr(documents, "get_object_storage", lambda: storage)

    with pytest.raises(HTTPException) as error:
        documents.download_revision_file(
            *identifiers, cast(Session, db), cast(AuthenticatedSession, object())
        )

    assert error.value.status_code == 409


def test_clean_revision_download_checks_integrity_and_sets_safe_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identifiers, resources = _inputs(monkeypatch, file_state="clean")
    db, _revision = resources
    payload = b"%PDF-test"
    storage = SimpleNamespace(get_object=lambda *_args: payload)
    monkeypatch.setattr(documents, "get_object_storage", lambda: storage)
    monkeypatch.setattr(
        documents, "get_settings", lambda: SimpleNamespace(s3_documents_bucket="private-documents")
    )

    response = documents.download_revision_file(
        *identifiers, cast(Session, db), cast(AuthenticatedSession, object())
    )

    assert response.body == payload
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-security-policy"] == "sandbox"


def test_clean_revision_with_tampered_payload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    identifiers, resources = _inputs(monkeypatch, file_state="clean")
    db, _revision = resources
    monkeypatch.setattr(
        documents,
        "get_object_storage",
        lambda: SimpleNamespace(get_object=lambda *_args: b"tampered"),
    )

    with pytest.raises(HTTPException) as error:
        documents.download_revision_file(
            *identifiers, cast(Session, db), cast(AuthenticatedSession, object())
        )

    assert error.value.status_code == 503


def _upload_context(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[UUID, UUID, SimpleNamespace, SimpleNamespace, SimpleNamespace, list[tuple[str, str]]]:
    tenant_id, user_id, unit_id = uuid4(), uuid4(), uuid4()
    document_id, revision_id = uuid4(), uuid4()
    actor = OrganizationActor(user_id, "Tester", "member", tenant_id)
    revision = SimpleNamespace(
        id=revision_id,
        document_id=document_id,
        tenant_id=tenant_id,
        revision="1",
        status="draft",
        prepared_by_user_id=user_id,
        reviewed_by_user_id=None,
        approved_by_user_id=None,
        effective_date=None,
        review_date=None,
        file_state="missing",
        row_version=1,
        file_object_key=None,
        file_sha256=None,
        file_size=None,
        file_media_type=None,
    )
    document = SimpleNamespace(id=document_id, tenant_id=tenant_id, unit_id=unit_id)
    rows = iter((revision, document))
    db = SimpleNamespace(
        scalar=lambda *_args: next(rows),
        flush=lambda: None,
        commit=lambda: None,
        rollback=lambda: None,
    )
    stored: list[tuple[str, str]] = []
    storage = SimpleNamespace(
        create_bucket=lambda _bucket: None,
        put_object=lambda _bucket, key, _payload: stored.append((_bucket, key)),
        delete_object=lambda *_args: None,
    )
    monkeypatch.setattr(documents, "actor_context", lambda *_args: actor)
    monkeypatch.setattr(documents, "require_capability", lambda *_args: None)
    monkeypatch.setattr(documents, "get_object_storage", lambda: storage)
    monkeypatch.setattr(
        documents, "get_settings", lambda: SimpleNamespace(s3_documents_bucket="private-documents")
    )
    monkeypatch.setattr(documents, "_commit", lambda *_args: None)
    return document_id, revision_id, revision, document, db, stored


def _upload_request(body: bytes) -> Request:
    messages = iter([{"type": "http.request", "body": body, "more_body": False}])

    async def receive() -> dict[str, object]:
        return next(messages)

    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/documents/file",
            "headers": [(b"content-type", b"application/pdf")],
            "query_string": b"",
        },
        receive=receive,
    )
    request.state.request_id = uuid4()
    return request


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [(ScanVerdict.CLEAN, "clean"), (ScanVerdict.INFECTED, "rejected")],
)
def test_upload_persists_only_scanned_verdict(
    monkeypatch: pytest.MonkeyPatch,
    verdict: ScanVerdict,
    expected: str,
) -> None:
    document_id, revision_id, revision, _document, db, stored = _upload_context(monkeypatch)
    monkeypatch.setattr(documents, "scan", lambda _payload: verdict)

    result = asyncio.run(
        documents.quarantine_revision_file(
            document_id,
            revision_id,
            _upload_request(b"%PDF-1.7\n%%EOF"),
            cast(Session, db),
            cast(AuthenticatedSession, object()),
        )
    )

    assert result["file_state"] == expected
    assert revision.file_state == expected
    assert stored and stored[0][0] == "private-documents"


def test_upload_fails_closed_and_does_not_store_without_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id, revision_id, revision, _document, db, stored = _upload_context(monkeypatch)

    def unavailable(_payload: object) -> ScanVerdict:
        raise ScanUnavailable("scanner unavailable")

    monkeypatch.setattr(documents, "scan", unavailable)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            documents.quarantine_revision_file(
                document_id,
                revision_id,
                _upload_request(b"%PDF-1.7\n%%EOF"),
                cast(Session, db),
                cast(AuthenticatedSession, object()),
            )
        )

    assert error.value.status_code == 503
    assert revision.file_state == "missing"
    assert not stored
