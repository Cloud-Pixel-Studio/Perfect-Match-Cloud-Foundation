"""Versioned, scoped risk references with immutable snapshots and soft removal."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import (
    QMSControlInstance,
    QMSDocument,
    QMSDocumentRevision,
    QMSRisk,
    QMSRiskControlLink,
    QMSRiskDocumentLink,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability
from pmc_api.risks import _db_error

router = APIRouter(prefix="/risks", tags=["risk-links"])
DBSession = Annotated[Session, Depends(get_db)]
Link = QMSRiskControlLink | QMSRiskDocumentLink


class ControlLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    control_instance_id: UUID


class DocumentLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    document_id: UUID
    document_revision_id: UUID


class LinkRemoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_link_version: int = Field(ge=1)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    risk_id: UUID
    unit_id: UUID
    target_process_id: UUID
    snapshot_code: str
    snapshot_name: str
    linked_target_version: int
    status: str
    row_version: int
    created_by_user_id: UUID
    created_at: datetime
    removed_by_user_id: UUID | None
    removed_at: datetime | None
    removal_reason: str
    risk_row_version: int
    target_state: str


class ControlLinkResponse(LinkResponse):
    control_instance_id: UUID


class DocumentLinkResponse(LinkResponse):
    document_id: UUID
    document_revision_id: UUID
    snapshot_revision: str
    file_sha256: str


def _parent(
    db: Session,
    actor: OrganizationActor,
    risk_id: UUID,
    target_capability: str,
    *,
    expected_version: int | None = None,
) -> QMSRisk:
    query = select(QMSRisk).where(QMSRisk.id == risk_id, QMSRisk.tenant_id == actor.tenant_id)
    if expected_version is not None:
        query = query.with_for_update().execution_options(populate_existing=True)
    risk = db.scalar(query)
    if risk is None:
        raise HTTPException(404, "risk not found")
    require_capability(db, "risks.read", risk.unit_id)
    require_capability(db, target_capability, risk.unit_id)
    if expected_version is not None:
        require_capability(db, "risks.manage", risk.unit_id)
        if risk.row_version != expected_version:
            raise HTTPException(409, "risk changed; refresh before changing related records")
        if risk.state == "closed":
            raise HTTPException(409, "closed risks are immutable")
    return risk


def _response(
    db: Session, row: Link, risk_version: int
) -> ControlLinkResponse | DocumentLinkResponse:
    data = {
        name: getattr(row, name)
        for name in LinkResponse.model_fields
        if name not in {"risk_row_version", "target_state"}
    }
    data["risk_row_version"] = risk_version
    if isinstance(row, QMSRiskControlLink):
        data["control_instance_id"] = row.control_instance_id
        data["target_state"] = (
            db.scalar(
                select(QMSControlInstance.status).where(
                    QMSControlInstance.id == row.control_instance_id,
                    QMSControlInstance.tenant_id == row.tenant_id,
                    QMSControlInstance.unit_id == row.unit_id,
                )
            )
            or "unavailable"
        )
        return ControlLinkResponse.model_validate(data)
    data.update(
        document_id=row.document_id,
        document_revision_id=row.document_revision_id,
        snapshot_revision=row.snapshot_revision,
        file_sha256=row.file_sha256,
    )
    target = db.execute(
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
    data["target_state"] = (
        ("obsolete" if target[0] == "obsolete" else target[1]) if target else "unavailable"
    )
    return DocumentLinkResponse.model_validate(data)


def _values(row: Link, risk_version: int) -> dict[str, object]:
    names = [
        "risk_id",
        "unit_id",
        "target_process_id",
        "snapshot_code",
        "snapshot_name",
        "linked_target_version",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "removed_by_user_id",
        "removed_at",
    ]
    names += (
        ["control_instance_id"]
        if isinstance(row, QMSRiskControlLink)
        else ["document_id", "document_revision_id", "snapshot_revision", "file_sha256"]
    )
    values: dict[str, object] = {}
    for name in names:
        value = getattr(row, name)
        values[name] = (
            str(value)
            if isinstance(value, UUID)
            else (value.isoformat() if isinstance(value, datetime) else value)
        )
    values["risk_row_version"] = risk_version
    values["removal_reason_hash"] = hashlib.sha256(row.removal_reason.encode()).hexdigest()
    return values


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    risk: QMSRisk,
    row: Link,
    action: str,
    before: dict[str, object] | None,
) -> ControlLinkResponse | DocumentLinkResponse:
    try:
        db.flush()
        # Snapshot fields and parent version are generated by the database trigger.
        db.refresh(row)
        db.refresh(risk)
        audit_service.record_risk_link(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(row, risk.row_version),
        )
        result = _response(db, row, risk.row_version)
        db.commit()
        return result
    except DBAPIError as error:
        _db_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


def create_control_link(
    db: Session, actor: OrganizationActor, request_id: UUID, risk_id: UUID, body: ControlLinkInput
) -> ControlLinkResponse:
    risk = _parent(
        db, actor, risk_id, "control_instances.read", expected_version=body.expected_version
    )
    row = QMSRiskControlLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=risk.unit_id,
        risk_id=risk.id,
        control_instance_id=body.control_instance_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        ControlLinkResponse, _finish(db, actor, request_id, risk, row, "risk.control_linked", None)
    )


def create_document_link(
    db: Session, actor: OrganizationActor, request_id: UUID, risk_id: UUID, body: DocumentLinkInput
) -> DocumentLinkResponse:
    risk = _parent(db, actor, risk_id, "documents.read", expected_version=body.expected_version)
    row = QMSRiskDocumentLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=risk.unit_id,
        risk_id=risk.id,
        document_id=body.document_id,
        document_revision_id=body.document_revision_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        DocumentLinkResponse,
        _finish(db, actor, request_id, risk, row, "risk.document_linked", None),
    )


def _remove(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    risk_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    kind: str,
) -> ControlLinkResponse | DocumentLinkResponse:
    control = kind == "control"
    risk = _parent(
        db,
        actor,
        risk_id,
        "control_instances.read" if control else "documents.read",
        expected_version=body.expected_version,
    )
    model = QMSRiskControlLink if control else QMSRiskDocumentLink
    row = cast(
        Link | None,
        db.scalar(
            select(model)
            .where(
                model.id == link_id,
                model.risk_id == risk.id,
                model.tenant_id == actor.tenant_id,
                model.unit_id == risk.unit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if row is None:
        raise HTTPException(404, "risk link not found")
    if row.status != "active" or row.row_version != body.expected_link_version:
        raise HTTPException(409, "risk link changed; refresh before removing it")
    before = _values(row, risk.row_version)
    row.status = "removed"
    row.removal_reason = body.reason
    row.row_version += 1
    return _finish(db, actor, request_id, risk, row, f"risk.{kind}_unlinked", before)


def remove_control_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    risk_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> ControlLinkResponse:
    return cast(
        ControlLinkResponse, _remove(db, actor, request_id, risk_id, link_id, body, "control")
    )


def remove_document_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    risk_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> DocumentLinkResponse:
    return cast(
        DocumentLinkResponse, _remove(db, actor, request_id, risk_id, link_id, body, "document")
    )


@router.get("/{risk_id}/control-links", response_model=list[ControlLinkResponse])
def list_control_links(
    db: DBSession,
    authenticated: Authenticated,
    risk_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[ControlLinkResponse]:
    actor = actor_context(db, authenticated)
    risk = _parent(db, actor, risk_id, "control_instances.read")
    rows = db.scalars(
        select(QMSRiskControlLink)
        .where(
            QMSRiskControlLink.risk_id == risk.id, QMSRiskControlLink.tenant_id == actor.tenant_id
        )
        .order_by(QMSRiskControlLink.created_at.desc(), QMSRiskControlLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(ControlLinkResponse, _response(db, row, risk.row_version)) for row in rows]


@router.get("/{risk_id}/document-links", response_model=list[DocumentLinkResponse])
def list_document_links(
    db: DBSession,
    authenticated: Authenticated,
    risk_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[DocumentLinkResponse]:
    actor = actor_context(db, authenticated)
    risk = _parent(db, actor, risk_id, "documents.read")
    rows = db.scalars(
        select(QMSRiskDocumentLink)
        .where(
            QMSRiskDocumentLink.risk_id == risk.id, QMSRiskDocumentLink.tenant_id == actor.tenant_id
        )
        .order_by(QMSRiskDocumentLink.created_at.desc(), QMSRiskDocumentLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(DocumentLinkResponse, _response(db, row, risk.row_version)) for row in rows]


@router.post(
    "/{risk_id}/control-links",
    response_model=ControlLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_control_route(
    request: Request,
    risk_id: UUID,
    body: ControlLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> ControlLinkResponse:
    return create_control_link(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, body
    )


@router.post(
    "/{risk_id}/document-links",
    response_model=DocumentLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_document_route(
    request: Request,
    risk_id: UUID,
    body: DocumentLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentLinkResponse:
    return create_document_link(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, body
    )


@router.post(
    "/{risk_id}/control-links/{link_id}/remove",
    response_model=ControlLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_control_route(
    request: Request,
    risk_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> ControlLinkResponse:
    return remove_control_link(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, link_id, body
    )


@router.post(
    "/{risk_id}/document-links/{link_id}/remove",
    response_model=DocumentLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_document_route(
    request: Request,
    risk_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentLinkResponse:
    return remove_document_link(
        db, actor_context(db, authenticated), request.state.request_id, risk_id, link_id, body
    )
