"""Versioned, scoped NCR references with immutable snapshots and soft removal."""

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
    QMSControlInstanceEvidence,
    QMSDocument,
    QMSDocumentRevision,
    QMSNCRControlLink,
    QMSNCRDocumentLink,
    QMSNCREvidenceLink,
    QMSNCRRiskLink,
    QMSNonconformity,
    QMSRisk,
)
from pmc_api.nonconformities import _db_error
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/nonconformities", tags=["ncr-links"])
DBSession = Annotated[Session, Depends(get_db)]
Link = QMSNCRRiskLink | QMSNCRControlLink | QMSNCRDocumentLink | QMSNCREvidenceLink


class RiskLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    risk_id: UUID


class ControlLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    control_instance_id: UUID


class EvidenceLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    evidence_id: UUID


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
    nonconformity_id: UUID
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
    ncr_row_version: int
    target_state: str


class RiskLinkResponse(LinkResponse):
    risk_id: UUID


class ControlLinkResponse(LinkResponse):
    control_instance_id: UUID


class EvidenceLinkResponse(LinkResponse):
    evidence_id: UUID
    control_instance_id: UUID


class DocumentLinkResponse(LinkResponse):
    document_id: UUID
    document_revision_id: UUID
    snapshot_revision: str
    file_sha256: str


def _parent(
    db: Session,
    actor: OrganizationActor,
    nonconformity_id: UUID,
    target_capability: str,
    *,
    expected_version: int | None = None,
) -> QMSNonconformity:
    query = select(QMSNonconformity).where(
        QMSNonconformity.id == nonconformity_id, QMSNonconformity.tenant_id == actor.tenant_id
    )
    if expected_version is not None:
        query = query.with_for_update().execution_options(populate_existing=True)
    ncr = db.scalar(query)
    if ncr is None:
        raise HTTPException(404, "ncr not found")
    require_capability(db, "ncr.read", ncr.unit_id)
    require_capability(db, target_capability, ncr.unit_id)
    if expected_version is not None:
        require_capability(db, "ncr.manage", ncr.unit_id)
        if ncr.row_version != expected_version:
            raise HTTPException(409, "ncr changed; refresh before changing related records")
        if ncr.state in {"closed", "cancelled"}:
            raise HTTPException(409, "closed or cancelled nonconformities are immutable")
    return ncr


def _response(
    db: Session, row: Link, ncr_version: int
) -> RiskLinkResponse | ControlLinkResponse | DocumentLinkResponse | EvidenceLinkResponse:
    data = {
        name: getattr(row, name)
        for name in LinkResponse.model_fields
        if name not in {"ncr_row_version", "target_state"}
    }
    data["ncr_row_version"] = ncr_version
    if isinstance(row, QMSNCRRiskLink):
        data["risk_id"] = row.risk_id
        data["target_state"] = (
            db.scalar(
                select(QMSRisk.state).where(
                    QMSRisk.id == row.risk_id,
                    QMSRisk.tenant_id == row.tenant_id,
                    QMSRisk.unit_id == row.unit_id,
                )
            )
            or "unavailable"
        )
        return RiskLinkResponse.model_validate(data)
    if isinstance(row, QMSNCRControlLink):
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
    if isinstance(row, QMSNCREvidenceLink):
        data["evidence_id"] = row.evidence_id
        data["control_instance_id"] = row.control_instance_id
        data["target_state"] = (
            db.scalar(
                select(QMSControlInstanceEvidence.status).where(
                    QMSControlInstanceEvidence.id == row.evidence_id,
                    QMSControlInstanceEvidence.tenant_id == row.tenant_id,
                    QMSControlInstanceEvidence.unit_id == row.unit_id,
                )
            )
            or "unavailable"
        )
        return EvidenceLinkResponse.model_validate(data)
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


def _values(row: Link, ncr_version: int) -> dict[str, object]:
    names = [
        "nonconformity_id",
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
        ["risk_id"]
        if isinstance(row, QMSNCRRiskLink)
        else (
            ["control_instance_id"]
            if isinstance(row, QMSNCRControlLink)
            else (
                ["evidence_id", "control_instance_id"]
                if isinstance(row, QMSNCREvidenceLink)
                else ["document_id", "document_revision_id", "snapshot_revision", "file_sha256"]
            )
        )
    )
    values: dict[str, object] = {}
    for name in names:
        value = getattr(row, name)
        values[name] = (
            str(value)
            if isinstance(value, UUID)
            else (value.isoformat() if isinstance(value, datetime) else value)
        )
    values["ncr_row_version"] = ncr_version
    values["removal_reason_hash"] = hashlib.sha256(row.removal_reason.encode()).hexdigest()
    return values


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    ncr: QMSNonconformity,
    row: Link,
    action: str,
    before: dict[str, object] | None,
) -> RiskLinkResponse | ControlLinkResponse | DocumentLinkResponse | EvidenceLinkResponse:
    try:
        db.flush()
        # Snapshot fields and parent version are generated by the database trigger.
        db.refresh(row)
        db.refresh(ncr)
        audit_service.record_ncr_link(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(row, ncr.row_version),
        )
        result = _response(db, row, ncr.row_version)
        db.commit()
        return result
    except DBAPIError as error:
        _db_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


def create_risk_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    body: RiskLinkInput,
) -> RiskLinkResponse:
    ncr = _parent(db, actor, nonconformity_id, "risks.read", expected_version=body.expected_version)
    row = QMSNCRRiskLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=ncr.unit_id,
        nonconformity_id=ncr.id,
        risk_id=body.risk_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(RiskLinkResponse, _finish(db, actor, request_id, ncr, row, "ncr.risk_linked", None))


def create_control_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    body: ControlLinkInput,
) -> ControlLinkResponse:
    ncr = _parent(
        db,
        actor,
        nonconformity_id,
        "control_instances.read",
        expected_version=body.expected_version,
    )
    row = QMSNCRControlLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=ncr.unit_id,
        nonconformity_id=ncr.id,
        control_instance_id=body.control_instance_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        ControlLinkResponse, _finish(db, actor, request_id, ncr, row, "ncr.control_linked", None)
    )


def create_evidence_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    body: EvidenceLinkInput,
) -> EvidenceLinkResponse:
    ncr = _parent(
        db,
        actor,
        nonconformity_id,
        "control_instances.read",
        expected_version=body.expected_version,
    )
    row = QMSNCREvidenceLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=ncr.unit_id,
        nonconformity_id=ncr.id,
        evidence_id=body.evidence_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        EvidenceLinkResponse, _finish(db, actor, request_id, ncr, row, "ncr.evidence_linked", None)
    )


def create_document_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    body: DocumentLinkInput,
) -> DocumentLinkResponse:
    ncr = _parent(
        db, actor, nonconformity_id, "documents.read", expected_version=body.expected_version
    )
    row = QMSNCRDocumentLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=ncr.unit_id,
        nonconformity_id=ncr.id,
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
        _finish(db, actor, request_id, ncr, row, "ncr.document_linked", None),
    )


def _remove(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    kind: str,
) -> RiskLinkResponse | ControlLinkResponse | DocumentLinkResponse | EvidenceLinkResponse:
    target_capability = {
        "risk": "risks.read",
        "control": "control_instances.read",
        "evidence": "control_instances.read",
        "document": "documents.read",
    }[kind]
    ncr = _parent(
        db,
        actor,
        nonconformity_id,
        target_capability,
        expected_version=body.expected_version,
    )
    models: dict[
        str,
        type[QMSNCRRiskLink]
        | type[QMSNCRControlLink]
        | type[QMSNCRDocumentLink]
        | type[QMSNCREvidenceLink],
    ] = {
        "risk": QMSNCRRiskLink,
        "control": QMSNCRControlLink,
        "evidence": QMSNCREvidenceLink,
        "document": QMSNCRDocumentLink,
    }
    model = models[kind]
    row = cast(
        Link | None,
        db.scalar(
            select(model)
            .where(
                model.id == link_id,
                model.nonconformity_id == ncr.id,
                model.tenant_id == actor.tenant_id,
                model.unit_id == ncr.unit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if row is None:
        raise HTTPException(404, "ncr link not found")
    if row.status != "active" or row.row_version != body.expected_link_version:
        raise HTTPException(409, "ncr link changed; refresh before removing it")
    before = _values(row, ncr.row_version)
    row.status = "removed"
    row.removal_reason = body.reason
    row.row_version += 1
    return _finish(db, actor, request_id, ncr, row, f"ncr.{kind}_unlinked", before)


def remove_risk_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> RiskLinkResponse:
    return cast(
        RiskLinkResponse, _remove(db, actor, request_id, nonconformity_id, link_id, body, "risk")
    )


def remove_control_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> ControlLinkResponse:
    return cast(
        ControlLinkResponse,
        _remove(db, actor, request_id, nonconformity_id, link_id, body, "control"),
    )


def remove_evidence_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> EvidenceLinkResponse:
    return cast(
        EvidenceLinkResponse,
        _remove(db, actor, request_id, nonconformity_id, link_id, body, "evidence"),
    )


def remove_document_link(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
) -> DocumentLinkResponse:
    return cast(
        DocumentLinkResponse,
        _remove(db, actor, request_id, nonconformity_id, link_id, body, "document"),
    )


@router.get("/{nonconformity_id}/risk-links", response_model=list[RiskLinkResponse])
def list_risk_links(
    db: DBSession,
    authenticated: Authenticated,
    nonconformity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[RiskLinkResponse]:
    actor = actor_context(db, authenticated)
    ncr = _parent(db, actor, nonconformity_id, "risks.read")
    rows = db.scalars(
        select(QMSNCRRiskLink)
        .where(
            QMSNCRRiskLink.nonconformity_id == ncr.id, QMSNCRRiskLink.tenant_id == actor.tenant_id
        )
        .order_by(QMSNCRRiskLink.created_at.desc(), QMSNCRRiskLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(RiskLinkResponse, _response(db, row, ncr.row_version)) for row in rows]


@router.get("/{nonconformity_id}/control-links", response_model=list[ControlLinkResponse])
def list_control_links(
    db: DBSession,
    authenticated: Authenticated,
    nonconformity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[ControlLinkResponse]:
    actor = actor_context(db, authenticated)
    ncr = _parent(db, actor, nonconformity_id, "control_instances.read")
    rows = db.scalars(
        select(QMSNCRControlLink)
        .where(
            QMSNCRControlLink.nonconformity_id == ncr.id,
            QMSNCRControlLink.tenant_id == actor.tenant_id,
        )
        .order_by(QMSNCRControlLink.created_at.desc(), QMSNCRControlLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(ControlLinkResponse, _response(db, row, ncr.row_version)) for row in rows]


@router.get("/{nonconformity_id}/document-links", response_model=list[DocumentLinkResponse])
def list_document_links(
    db: DBSession,
    authenticated: Authenticated,
    nonconformity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[DocumentLinkResponse]:
    actor = actor_context(db, authenticated)
    ncr = _parent(db, actor, nonconformity_id, "documents.read")
    rows = db.scalars(
        select(QMSNCRDocumentLink)
        .where(
            QMSNCRDocumentLink.nonconformity_id == ncr.id,
            QMSNCRDocumentLink.tenant_id == actor.tenant_id,
        )
        .order_by(QMSNCRDocumentLink.created_at.desc(), QMSNCRDocumentLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(DocumentLinkResponse, _response(db, row, ncr.row_version)) for row in rows]


@router.get("/{nonconformity_id}/evidence-links", response_model=list[EvidenceLinkResponse])
def list_evidence_links(
    db: DBSession,
    authenticated: Authenticated,
    nonconformity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[EvidenceLinkResponse]:
    actor = actor_context(db, authenticated)
    ncr = _parent(db, actor, nonconformity_id, "control_instances.read")
    rows = db.scalars(
        select(QMSNCREvidenceLink)
        .where(
            QMSNCREvidenceLink.nonconformity_id == ncr.id,
            QMSNCREvidenceLink.tenant_id == actor.tenant_id,
        )
        .order_by(QMSNCREvidenceLink.created_at.desc(), QMSNCREvidenceLink.id)
        .limit(limit)
        .offset(offset)
    )
    return [cast(EvidenceLinkResponse, _response(db, row, ncr.row_version)) for row in rows]


@router.post(
    "/{nonconformity_id}/risk-links",
    response_model=RiskLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_risk_route(
    request: Request,
    nonconformity_id: UUID,
    body: RiskLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> RiskLinkResponse:
    return create_risk_link(
        db, actor_context(db, authenticated), request.state.request_id, nonconformity_id, body
    )


@router.post(
    "/{nonconformity_id}/control-links",
    response_model=ControlLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_control_route(
    request: Request,
    nonconformity_id: UUID,
    body: ControlLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> ControlLinkResponse:
    return create_control_link(
        db, actor_context(db, authenticated), request.state.request_id, nonconformity_id, body
    )


@router.post(
    "/{nonconformity_id}/document-links",
    response_model=DocumentLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_document_route(
    request: Request,
    nonconformity_id: UUID,
    body: DocumentLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentLinkResponse:
    return create_document_link(
        db, actor_context(db, authenticated), request.state.request_id, nonconformity_id, body
    )


@router.post(
    "/{nonconformity_id}/evidence-links",
    response_model=EvidenceLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_evidence_route(
    request: Request,
    nonconformity_id: UUID,
    body: EvidenceLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> EvidenceLinkResponse:
    return create_evidence_link(
        db, actor_context(db, authenticated), request.state.request_id, nonconformity_id, body
    )


@router.post(
    "/{nonconformity_id}/risk-links/{link_id}/remove",
    response_model=RiskLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_risk_route(
    request: Request,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> RiskLinkResponse:
    return remove_risk_link(
        db,
        actor_context(db, authenticated),
        request.state.request_id,
        nonconformity_id,
        link_id,
        body,
    )


@router.post(
    "/{nonconformity_id}/control-links/{link_id}/remove",
    response_model=ControlLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_control_route(
    request: Request,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> ControlLinkResponse:
    return remove_control_link(
        db,
        actor_context(db, authenticated),
        request.state.request_id,
        nonconformity_id,
        link_id,
        body,
    )


@router.post(
    "/{nonconformity_id}/document-links/{link_id}/remove",
    response_model=DocumentLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_document_route(
    request: Request,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentLinkResponse:
    return remove_document_link(
        db,
        actor_context(db, authenticated),
        request.state.request_id,
        nonconformity_id,
        link_id,
        body,
    )


@router.post(
    "/{nonconformity_id}/evidence-links/{link_id}/remove",
    response_model=EvidenceLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_evidence_route(
    request: Request,
    nonconformity_id: UUID,
    link_id: UUID,
    body: LinkRemoveInput,
    db: DBSession,
    authenticated: Authenticated,
) -> EvidenceLinkResponse:
    return remove_evidence_link(
        db,
        actor_context(db, authenticated),
        request.state.request_id,
        nonconformity_id,
        link_id,
        body,
    )
