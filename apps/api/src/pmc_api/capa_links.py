"""Controlled CAPA references to clean, released document revisions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.capa import _row
from pmc_api.database import get_db
from pmc_api.models import QMSCAPA, QMSCAPADocumentLink, QMSDocument, QMSDocumentRevision
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/capas", tags=["capa-links"])
DBSession = Annotated[Session, Depends(get_db)]


class CAPADocumentLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    document_id: UUID
    document_revision_id: UUID


class CAPADocumentLinkRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_link_version: int = Field(ge=1)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CAPADocumentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    capa_id: UUID
    unit_id: UUID
    document_id: UUID
    document_revision_id: UUID
    target_process_id: UUID
    snapshot_code: str
    snapshot_name: str
    snapshot_revision: str
    file_sha256: str
    linked_target_version: int
    status: str
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    removed_by_user_id: UUID | None
    removed_at: datetime | None
    removal_reason: str
    capa_row_version: int
    target_state: str


def _parent(
    db: Session,
    actor: OrganizationActor,
    capa_id: UUID,
    expected_version: int | None = None,
) -> QMSCAPA:
    parent = _row(db, actor, capa_id, lock=expected_version is not None)
    require_capability(db, "documents.read", parent.unit_id)
    if expected_version is not None:
        require_capability(db, "capa.manage", parent.unit_id)
        if parent.row_version != expected_version:
            raise HTTPException(409, "CAPA changed; refresh related documents")
        if parent.state not in {"draft", "analysis", "action_planned", "implementation"}:
            raise HTTPException(
                409, "CAPA document links are locked during review or after termination"
            )
    return parent


def _response(
    db: Session, row: QMSCAPADocumentLink, parent_version: int
) -> CAPADocumentLinkResponse:
    data = {
        name: getattr(row, name)
        for name in CAPADocumentLinkResponse.model_fields
        if name not in {"capa_row_version", "target_state"}
    }
    current = db.execute(
        select(QMSDocument.status, QMSDocumentRevision.status)
        .join(
            QMSDocumentRevision,
            (QMSDocumentRevision.document_id == QMSDocument.id)
            & (QMSDocumentRevision.tenant_id == QMSDocument.tenant_id),
        )
        .where(
            QMSDocument.id == row.document_id,
            QMSDocument.tenant_id == row.tenant_id,
            QMSDocument.unit_id == row.unit_id,
            QMSDocumentRevision.id == row.document_revision_id,
        )
    ).first()
    data["capa_row_version"] = parent_version
    data["target_state"] = (
        ("obsolete" if current[0] == "obsolete" else current[1]) if current else "unavailable"
    )
    return CAPADocumentLinkResponse.model_validate(data)


def _values(row: QMSCAPADocumentLink, parent_version: int) -> dict[str, object]:
    names = [
        "capa_id",
        "unit_id",
        "document_id",
        "document_revision_id",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "snapshot_revision",
        "file_sha256",
        "linked_target_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
    ]
    values: dict[str, object] = {}
    for name in names:
        value = getattr(row, name)
        values[name] = (
            str(value)
            if isinstance(value, UUID)
            else (value.isoformat() if isinstance(value, datetime) else value)
        )
    values["capa_row_version"] = parent_version
    values["removal_reason_hash"] = hashlib.sha256(row.removal_reason.encode()).hexdigest()
    return values


def _db_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(
            409, "CAPA document link conflicts with its scope, version or state"
        ) from None
    if state == "42501":
        raise HTTPException(403, "CAPA document link authority denied") from None
    raise error


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    parent: QMSCAPA,
    row: QMSCAPADocumentLink,
    action: str,
    before: dict[str, object] | None,
) -> CAPADocumentLinkResponse:
    try:
        db.execute(
            text("SELECT set_config('app.capa_link_command',:command,true)"),
            {"command": "link" if action == "capa.document_linked" else "unlink"},
        )
        db.flush()
        db.refresh(row)
        db.refresh(parent)
        audit_service.record_capa_document_link(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(row, parent.row_version),
        )
        result = _response(db, row, parent.row_version)
        db.commit()
        return result
    except DBAPIError as error:
        _db_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


@router.get("/{capa_id}/document-links", response_model=list[CAPADocumentLinkResponse])
def list_document_links(
    capa_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[CAPADocumentLinkResponse]:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id)
    rows = db.scalars(
        select(QMSCAPADocumentLink)
        .where(
            QMSCAPADocumentLink.capa_id == parent.id,
            QMSCAPADocumentLink.tenant_id == actor.tenant_id,
            QMSCAPADocumentLink.unit_id == parent.unit_id,
        )
        .order_by(QMSCAPADocumentLink.created_at.desc(), QMSCAPADocumentLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [_response(db, row, parent.row_version) for row in rows]


@router.post(
    "/{capa_id}/document-links",
    response_model=CAPADocumentLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_document_link(
    request: Request,
    capa_id: UUID,
    body: CAPADocumentLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPADocumentLinkResponse:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id, body.expected_version)
    row = QMSCAPADocumentLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=parent.unit_id,
        capa_id=parent.id,
        document_id=body.document_id,
        document_revision_id=body.document_revision_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return _finish(db, actor, request.state.request_id, parent, row, "capa.document_linked", None)


@router.post(
    "/{capa_id}/document-links/{link_id}/remove",
    response_model=CAPADocumentLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_document_link(
    request: Request,
    capa_id: UUID,
    link_id: UUID,
    body: CAPADocumentLinkRemove,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPADocumentLinkResponse:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id, body.expected_version)
    row = db.scalar(
        select(QMSCAPADocumentLink)
        .where(
            QMSCAPADocumentLink.id == link_id,
            QMSCAPADocumentLink.capa_id == parent.id,
            QMSCAPADocumentLink.tenant_id == actor.tenant_id,
            QMSCAPADocumentLink.unit_id == parent.unit_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "CAPA document link not found")
    if row.status != "active" or row.row_version != body.expected_link_version:
        raise HTTPException(409, "CAPA document link changed; refresh before removing")
    before = _values(row, parent.row_version)
    row.status = "removed"
    row.removal_reason = body.reason
    row.row_version += 1
    return _finish(
        db, actor, request.state.request_id, parent, row, "capa.document_unlinked", before
    )
