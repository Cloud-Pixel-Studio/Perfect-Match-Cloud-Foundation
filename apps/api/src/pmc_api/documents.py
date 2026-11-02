"""Scoped controlled documents and revision commands."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from datetime import UTC, date, datetime
from typing import Annotated, BinaryIO, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.antivirus import ScanUnavailable, ScanVerdict, scan
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.config import get_settings
from pmc_api.database import get_db
from pmc_api.models import QMSDocument, QMSDocumentRevision, QMSProcess
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability
from pmc_api.storage import get_object_storage

router = APIRouter(prefix="/documents", tags=["documents"])
DB = Annotated[Session, Depends(get_db)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_upload_gate = asyncio.Lock()
_active_uploads = 0
_max_concurrent_uploads = 4
_document_view_capabilities = (
    "documents.read",
    "documents.author",
    "documents.review",
    "documents.approve",
    "documents.release",
    "documents.obsolete",
)


def require_document_view(db: Session, unit_id: UUID) -> None:
    """Match the document/revision SELECT policy with an explicit API denial."""
    if not any(
        db.scalar(
            text("SELECT qms_has_capability(:capability, :unit)"),
            {"capability": capability, "unit": unit_id},
        )
        for capability in _document_view_capabilities
    ):
        raise HTTPException(403, "document responsibility is not granted for this scope")


async def upload_capacity() -> AsyncIterator[None]:
    global _active_uploads
    async with _upload_gate:
        if _active_uploads >= _max_concurrent_uploads:
            raise HTTPException(503, "document upload capacity is temporarily full")
        _active_uploads += 1
    try:
        yield
    finally:
        async with _upload_gate:
            _active_uploads -= 1


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UUID
    process_id: UUID
    code: Code
    title: Title
    document_type: str = Field(
        pattern="^(policy|procedure|work_instruction|form|record_template|manual|other)$"
    )
    owner_user_id: UUID | None = None


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    change_summary: str = Field(default="", max_length=4000)
    revision_date: date = Field(default_factory=date.today)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    process_id: UUID
    code: str
    title: str
    document_type: str
    owner_user_id: UUID | None
    status: str
    current_revision_id: UUID | None
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class RevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    document_id: UUID
    revision: str
    status: str
    prepared_by_user_id: UUID
    prepared_by_display_name: str | None = None
    reviewed_by_user_id: UUID | None
    reviewed_by_display_name: str | None = None
    approved_by_user_id: UUID | None
    approved_by_display_name: str | None = None
    change_summary: str
    revision_date: date
    effective_date: date | None
    review_date: date | None
    file_state: str
    file_sha256: str | None
    file_size: int | None
    file_media_type: str | None
    row_version: int
    created_at: datetime


class ProcessReferenceResponse(BaseModel):
    id: UUID
    code: str
    name: str


def _revision_response(db: Session, revision: QMSDocumentRevision) -> RevisionResponse:
    names = {
        row.user_id: row.display_name
        for row in db.execute(
            text("SELECT user_id, display_name FROM organization_member_directory()")
        )
    }
    return RevisionResponse.model_validate(revision).model_copy(
        update={
            "prepared_by_display_name": names.get(revision.prepared_by_user_id),
            "reviewed_by_display_name": names.get(revision.reviewed_by_user_id),
            "approved_by_display_name": names.get(revision.approved_by_user_id),
        }
    )


@router.get("/processes", response_model=list[ProcessReferenceResponse])
def document_processes(
    db: DB,
    auth: Authenticated,
    unit_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    search: Annotated[str, Query(max_length=160)] = "",
) -> list[ProcessReferenceResponse]:
    actor = actor_context(db, auth)
    require_capability(db, "documents.author", unit_id)
    require_capability(db, "processes.read", unit_id)
    query = select(QMSProcess).where(
        QMSProcess.tenant_id == actor.tenant_id,
        QMSProcess.unit_id == unit_id,
        QMSProcess.status == "active",
    )
    if search.strip():
        pattern = (
            "%" + search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        )
        query = query.where(
            QMSProcess.code.ilike(pattern, escape="!") | QMSProcess.name.ilike(pattern, escape="!")
        )
    rows = db.scalars(query.order_by(QMSProcess.code, QMSProcess.id).limit(limit).offset(offset))
    return [ProcessReferenceResponse(id=row.id, code=row.code, name=row.name) for row in rows]


def _audit(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    action: str,
    resource: UUID,
    old: dict[str, object] | None,
    new: dict[str, object],
) -> None:
    audit_service.record_document(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=resource,
        request_id=request_id,
        old_values=old,
        new_values=new,
    )


def _commit(
    db: Session,
    actor: OrganizationActor,
    request: Request,
    action: str,
    resource: UUID,
    old: dict[str, object] | None,
    new: dict[str, object],
) -> None:
    try:
        _audit(db, actor, request.state.request_id, action, resource, old, new)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _dvalues(d: QMSDocument) -> dict[str, object]:
    return {
        "unit_id": str(d.unit_id),
        "process_id": str(d.process_id),
        "code": d.code,
        "title": d.title,
        "document_type": d.document_type,
        "owner_user_id": str(d.owner_user_id) if d.owner_user_id else None,
        "status": d.status,
        "current_revision_id": str(d.current_revision_id) if d.current_revision_id else None,
        "row_version": d.row_version,
    }


def _rvalues(r: QMSDocumentRevision) -> dict[str, object]:
    return {
        "document_id": str(r.document_id),
        "revision": r.revision,
        "status": r.status,
        "prepared_by_user_id": str(r.prepared_by_user_id),
        "reviewed_by_user_id": str(r.reviewed_by_user_id) if r.reviewed_by_user_id else None,
        "approved_by_user_id": str(r.approved_by_user_id) if r.approved_by_user_id else None,
        "file_state": r.file_state,
        "file_sha256": r.file_sha256,
        "file_size": r.file_size,
        "row_version": r.row_version,
        "effective_date": r.effective_date.isoformat() if r.effective_date else None,
        "review_date": r.review_date.isoformat() if r.review_date else None,
    }


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    db: DB,
    auth: Authenticated,
    unit_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    search: Annotated[str, Query(max_length=160)] = "",
) -> list[QMSDocument]:
    actor = actor_context(db, auth)
    require_document_view(db, unit_id)
    query = select(QMSDocument).where(
        QMSDocument.tenant_id == actor.tenant_id, QMSDocument.unit_id == unit_id
    )
    if search.strip():
        pattern = (
            "%" + search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        )
        query = query.where(
            or_(
                QMSDocument.code.ilike(pattern, escape="!"),
                QMSDocument.title.ilike(pattern, escape="!"),
            )
        )
    return list(
        db.scalars(query.order_by(QMSDocument.code, QMSDocument.id).limit(limit + 1).offset(offset))
    )


@router.post(
    "", status_code=201, response_model=DocumentResponse, dependencies=[Depends(require_csrf)]
)
def create_document(
    request: Request, body: DocumentInput, db: DB, auth: Authenticated
) -> QMSDocument:
    actor = actor_context(db, auth)
    require_capability(db, "documents.author", body.unit_id)
    require_capability(db, "processes.read", body.unit_id)
    now = datetime.now(UTC)
    row = QMSDocument(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        **body.model_dump(),
        status="draft",
        current_revision_id=None,
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _commit(db, actor, request, "document.created", row.id, None, _dvalues(row))
    except DBAPIError as e:
        db.rollback()
        raise HTTPException(409, "document scope or code is invalid") from e
    return row


@router.post(
    "/{document_id}/obsolete",
    response_model=DocumentResponse,
    dependencies=[Depends(require_csrf)],
)
def obsolete_document(
    document_id: UUID,
    request: Request,
    command: Command,
    db: DB,
    auth: Authenticated,
) -> QMSDocument:
    actor = actor_context(db, auth)
    document = db.scalar(
        select(QMSDocument)
        .where(QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None:
        raise HTTPException(404, "document not found")
    require_capability(db, "documents.obsolete", document.unit_id)
    if document.row_version != command.expected_version:
        raise HTTPException(409, "document changed; refresh before retrying")
    if document.status == "obsolete":
        raise HTTPException(409, "document is already obsolete")
    before = _dvalues(document)
    document.status = "obsolete"
    document.row_version += 1
    document.updated_at = datetime.now(UTC)
    try:
        db.flush()
        _commit(db, actor, request, "document.obsoleted", document.id, before, _dvalues(document))
    except Exception:
        db.rollback()
        raise
    return document


@router.get("/{document_id}/revisions", response_model=list[RevisionResponse])
def revisions(document_id: UUID, db: DB, auth: Authenticated) -> list[RevisionResponse]:
    actor = actor_context(db, auth)
    document = db.scalar(
        select(QMSDocument).where(
            QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id
        )
    )
    if document is None:
        raise HTTPException(404, "document not found")
    require_document_view(db, document.unit_id)
    names = {
        row.user_id: row.display_name
        for row in db.execute(
            text("SELECT user_id, display_name FROM organization_member_directory()")
        )
    }
    rows = db.scalars(
        select(QMSDocumentRevision)
        .where(
            QMSDocumentRevision.document_id == document_id,
            QMSDocumentRevision.tenant_id == actor.tenant_id,
        )
        .order_by(QMSDocumentRevision.created_at.desc())
        .limit(100)
    )
    return [
        RevisionResponse.model_validate(revision).model_copy(
            update={
                "prepared_by_display_name": names.get(revision.prepared_by_user_id),
                "reviewed_by_display_name": names.get(revision.reviewed_by_user_id),
                "approved_by_display_name": names.get(revision.approved_by_user_id),
            }
        )
        for revision in rows
    ]


@router.post(
    "/{document_id}/revisions",
    status_code=201,
    response_model=RevisionResponse,
    dependencies=[Depends(require_csrf)],
)
def create_revision(
    document_id: UUID, request: Request, body: RevisionInput, db: DB, auth: Authenticated
) -> RevisionResponse:
    actor = actor_context(db, auth)
    doc = db.scalar(
        select(QMSDocument)
        .where(QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id)
        .with_for_update()
    )
    if doc is None:
        raise HTTPException(404, "document not found")
    require_capability(db, "documents.author", doc.unit_id)
    if doc.status == "obsolete":
        raise HTTPException(409, "obsolete document cannot receive revisions")
    now = datetime.now(UTC)
    row = QMSDocumentRevision(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        document_id=doc.id,
        **body.model_dump(exclude={"revision_date"}),
        revision_date=body.revision_date,
        status="draft",
        prepared_by_user_id=actor.user_id,
        reviewed_by_user_id=None,
        approved_by_user_id=None,
        effective_date=None,
        review_date=None,
        file_state="missing",
        file_object_key=None,
        file_sha256=None,
        file_size=None,
        file_media_type=None,
        row_version=1,
        created_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _commit(db, actor, request, "revision.created", row.id, None, _rvalues(row))
    except DBAPIError as e:
        db.rollback()
        raise HTTPException(409, "revision code already exists or document is invalid") from e
    actor_context(db, auth)
    return _revision_response(db, row)


def transition_revision(
    document_id: UUID,
    revision_id: UUID,
    command: Command,
    action: str,
    db: Session,
    auth: Authenticated,
    request: Request,
) -> QMSDocumentRevision:
    actor = actor_context(db, auth)
    revision = db.scalar(
        select(QMSDocumentRevision)
        .where(
            QMSDocumentRevision.id == revision_id,
            QMSDocumentRevision.document_id == document_id,
            QMSDocumentRevision.tenant_id == actor.tenant_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if revision is None:
        raise HTTPException(404, "revision not found")
    doc = db.scalar(
        select(QMSDocument)
        .where(QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if doc is None:
        raise HTTPException(404, "document not found")
    if revision.row_version != command.expected_version:
        raise HTTPException(409, "revision changed; refresh before retrying")
    before = _rvalues(revision)
    if action == "submit":
        require_capability(db, "documents.review", doc.unit_id)
        if revision.status not in {"draft", "rejected"}:
            raise HTTPException(409, "only draft or rejected revisions can be submitted")
        revision.status = "under_review"
    elif action == "approve":
        require_capability(db, "documents.approve", doc.unit_id)
        if revision.status != "under_review" or revision.prepared_by_user_id == actor.user_id:
            raise HTTPException(403, "revision cannot be approved by its preparer or in this state")
        if revision.file_state != "clean":
            raise HTTPException(409, "revision file must pass the configured security scan")
        revision.status = "approved"
        revision.reviewed_by_user_id = actor.user_id
        revision.approved_by_user_id = actor.user_id
        revision.review_date = datetime.now(UTC).date()
    elif action == "reject":
        require_capability(db, "documents.review", doc.unit_id)
        if revision.status != "under_review":
            raise HTTPException(409, "only revisions under review can be rejected")
        revision.status = "rejected"
        revision.reviewed_by_user_id = actor.user_id
        revision.review_date = datetime.now(UTC).date()
    elif action == "release":
        require_capability(db, "documents.release", doc.unit_id)
        if revision.status != "approved" or revision.file_state != "clean":
            raise HTTPException(409, "only approved revisions with clean files can be released")
        previous = db.scalar(
            select(QMSDocumentRevision)
            .where(
                QMSDocumentRevision.document_id == document_id,
                QMSDocumentRevision.status == "active",
            )
            .with_for_update()
        )
        if previous is not None:
            previous.status = "superseded"
            previous.row_version += 1
        revision.status = "active"
        revision.reviewed_by_user_id = revision.reviewed_by_user_id or actor.user_id
        revision.effective_date = revision.effective_date or datetime.now(UTC).date()
        doc.status = "active"
        doc.current_revision_id = revision.id
        doc.row_version += 1
        doc.updated_at = datetime.now(UTC)
    revision.row_version += 1
    try:
        db.flush()
        _commit(
            db,
            actor,
            request,
            "revision."
            + (
                "released"
                if action == "release"
                else "approved"
                if action == "approve"
                else "rejected"
                if action == "reject"
                else "submitted"
            ),
            revision.id,
            before,
            _rvalues(revision),
        )
    except Exception:
        db.rollback()
        raise
    return revision


for _action in ("submit", "approve", "reject", "release"):

    def _endpoint_factory(action: str) -> Callable[..., RevisionResponse]:
        def endpoint(
            document_id: UUID,
            revision_id: UUID,
            request: Request,
            body: Command,
            db: DB,
            auth: Authenticated,
        ) -> RevisionResponse:
            revision = transition_revision(
                document_id, revision_id, body, action, db, auth, request
            )
            actor_context(db, auth)
            return _revision_response(db, revision)

        return endpoint

    router.add_api_route(
        "/{document_id}/revisions/{revision_id}/" + _action,
        _endpoint_factory(_action),
        methods=["POST"],
        response_model=RevisionResponse,
        dependencies=[Depends(require_csrf)],
    )


@router.put(
    "/{document_id}/revisions/{revision_id}/file",
    status_code=202,
    dependencies=[Depends(require_csrf), Depends(upload_capacity)],
)
async def quarantine_revision_file(
    document_id: UUID, revision_id: UUID, request: Request, db: DB, auth: Authenticated
) -> dict[str, object]:
    from botocore.exceptions import ClientError

    actor = actor_context(db, auth)
    revision = db.scalar(
        select(QMSDocumentRevision)
        .where(
            QMSDocumentRevision.id == revision_id,
            QMSDocumentRevision.document_id == document_id,
            QMSDocumentRevision.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    if revision is None:
        raise HTTPException(404, "revision not found")
    doc = db.scalar(
        select(QMSDocument).where(
            QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id
        )
    )
    if doc is None:
        raise HTTPException(404, "document not found")
    require_capability(db, "documents.author", doc.unit_id)
    if revision.status != "draft" or revision.file_state != "missing":
        raise HTTPException(409, "only draft revisions without a file accept uploads")
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/pdf":
        raise HTTPException(415, "only PDF files are accepted")
    maximum = 20 * 1024 * 1024
    total = 0
    digest = hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=maximum, mode="w+b") as payload:
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                raise HTTPException(413, "document exceeds 20 MiB")
            if chunk:
                digest.update(chunk)
                payload.write(chunk)
        payload.seek(0)
        if total < 8 or payload.read(5) != b"%PDF-":
            raise HTTPException(415, "file is not a valid PDF")
        payload.seek(0)
        try:
            verdict = scan(cast(BinaryIO, payload))
        except ScanUnavailable as error:
            raise HTTPException(503, "document security scan unavailable; retry upload") from error
        payload.seek(0)
        storage = get_object_storage()
        bucket = get_settings().s3_documents_bucket
        try:
            storage.create_bucket(bucket)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            }:
                raise HTTPException(503, "private document storage unavailable") from error
        key = f"qms/{actor.tenant_id}/{doc.id}/{revision.id}/{uuid4().hex}"
        storage.put_object(bucket, key, cast(BinaryIO, payload))
    before = _rvalues(revision)
    revision.file_object_key = key
    revision.file_sha256 = digest.hexdigest()
    revision.file_size = total
    revision.file_media_type = "application/pdf"
    revision.file_state = "clean" if verdict is ScanVerdict.CLEAN else "rejected"
    revision.row_version += 1
    try:
        db.flush()
        _commit(db, actor, request, "revision.updated", revision.id, before, _rvalues(revision))
    except Exception:
        db.rollback()
        with suppress(Exception):
            storage.delete_object(bucket, key)
        raise
    return {
        "revision_id": str(revision.id),
        "file_state": revision.file_state,
        "sha256": revision.file_sha256,
        "size": total,
    }


@router.get("/{document_id}/revisions/{revision_id}/file")
def download_revision_file(
    document_id: UUID, revision_id: UUID, db: DB, auth: Authenticated
) -> Response:
    actor = actor_context(db, auth)
    revision = db.scalar(
        select(QMSDocumentRevision).where(
            QMSDocumentRevision.id == revision_id,
            QMSDocumentRevision.document_id == document_id,
            QMSDocumentRevision.tenant_id == actor.tenant_id,
        )
    )
    if revision is None:
        raise HTTPException(404, "revision not found")
    doc = db.scalar(
        select(QMSDocument).where(
            QMSDocument.id == document_id, QMSDocument.tenant_id == actor.tenant_id
        )
    )
    if doc is None:
        raise HTTPException(404, "document not found")
    require_capability(db, "documents.read", doc.unit_id)
    if (
        revision.file_state != "clean"
        or revision.file_object_key is None
        or revision.file_sha256 is None
        or revision.file_size is None
    ):
        raise HTTPException(409, "revision file is not available for download")
    try:
        content = get_object_storage().get_object(
            get_settings().s3_documents_bucket, revision.file_object_key
        )
    except Exception as error:
        raise HTTPException(503, "private document storage unavailable") from error
    if (
        len(content) != revision.file_size
        or hashlib.sha256(content).hexdigest() != revision.file_sha256
    ):
        raise HTTPException(503, "stored document integrity check failed")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="qms-document-revision.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )
