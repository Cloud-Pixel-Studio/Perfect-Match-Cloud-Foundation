"""Direct, versioned CAPA references to control implementations and accepted evidence."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal, cast
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
from pmc_api.models import (
    QMSCAPA,
    QMSCAPAControlLink,
    QMSCAPAEvidenceLink,
    QMSControlInstance,
    QMSControlInstanceEvidence,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/capas", tags=["capa-trace-links"])
DBSession = Annotated[Session, Depends(get_db)]
TraceLink = QMSCAPAControlLink | QMSCAPAEvidenceLink
Kind = Literal["control", "evidence"]


class CAPAControlLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    control_instance_id: UUID


class CAPAEvidenceLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    evidence_id: UUID


class CAPATraceLinkRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_link_version: int = Field(ge=1)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CAPATraceLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    capa_id: UUID
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
    capa_row_version: int
    target_state: str


class CAPAControlLinkResponse(CAPATraceLinkResponse):
    control_instance_id: UUID


class CAPAEvidenceLinkResponse(CAPATraceLinkResponse):
    evidence_id: UUID
    control_instance_id: UUID


def _parent(
    db: Session,
    actor: OrganizationActor,
    capa_id: UUID,
    expected_version: int | None = None,
) -> QMSCAPA:
    parent = _row(db, actor, capa_id, lock=expected_version is not None)
    require_capability(db, "control_instances.read", parent.unit_id)
    if expected_version is not None:
        require_capability(db, "capa.manage", parent.unit_id)
        if parent.row_version != expected_version:
            raise HTTPException(409, "CAPA changed; refresh related controls and evidence")
        if parent.state not in {"draft", "analysis", "action_planned", "implementation"}:
            raise HTTPException(
                409, "CAPA trace links are locked during review or after termination"
            )
    return parent


def _target_state(db: Session, row: TraceLink, kind: Kind) -> str:
    if kind == "control":
        current = db.scalar(
            select(QMSControlInstance.implementation_status).where(
                QMSControlInstance.id == cast(QMSCAPAControlLink, row).control_instance_id,
                QMSControlInstance.tenant_id == row.tenant_id,
                QMSControlInstance.unit_id == row.unit_id,
                QMSControlInstance.status == "active",
            )
        )
    else:
        current = db.scalar(
            select(QMSControlInstanceEvidence.status).where(
                QMSControlInstanceEvidence.id == cast(QMSCAPAEvidenceLink, row).evidence_id,
                QMSControlInstanceEvidence.tenant_id == row.tenant_id,
                QMSControlInstanceEvidence.unit_id == row.unit_id,
            )
        )
    return current or "unavailable"


def _response(
    db: Session, row: TraceLink, parent_version: int, kind: Kind
) -> CAPAControlLinkResponse | CAPAEvidenceLinkResponse:
    response = CAPAControlLinkResponse if kind == "control" else CAPAEvidenceLinkResponse
    data = {
        name: getattr(row, name)
        for name in response.model_fields
        if name not in {"capa_row_version", "target_state"}
    }
    data["capa_row_version"] = parent_version
    data["target_state"] = _target_state(db, row, kind)
    return response.model_validate(data)


def _values(row: TraceLink, parent_version: int, kind: Kind) -> dict[str, object]:
    names = [
        "capa_id",
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
        "control_instance_id",
    ]
    if kind == "evidence":
        names.append("evidence_id")
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
            409, "CAPA trace link conflicts with its scope, target version or state"
        ) from None
    if state == "42501":
        raise HTTPException(403, "CAPA trace link authority denied") from None
    raise error


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    parent: QMSCAPA,
    row: TraceLink,
    action: str,
    kind: Kind,
    before: dict[str, object] | None,
) -> CAPAControlLinkResponse | CAPAEvidenceLinkResponse:
    try:
        db.execute(
            text("SELECT set_config('app.capa_link_command',:command,true)"),
            {"command": "link" if action.endswith("_linked") else "unlink"},
        )
        db.flush()
        db.refresh(row)
        db.refresh(parent)
        audit_service.record_capa_trace_link(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=action,
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(row, parent.row_version, kind),
        )
        result = _response(db, row, parent.row_version, kind)
        db.commit()
        return result
    except DBAPIError as error:
        _db_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


def _list(
    db: Session,
    actor: OrganizationActor,
    capa_id: UUID,
    kind: Kind,
    limit: int,
    offset: int,
) -> list[CAPAControlLinkResponse] | list[CAPAEvidenceLinkResponse]:
    parent = _parent(db, actor, capa_id)
    model = QMSCAPAControlLink if kind == "control" else QMSCAPAEvidenceLink
    rows = db.scalars(
        select(model)
        .where(
            model.capa_id == parent.id,
            model.tenant_id == actor.tenant_id,
            model.unit_id == parent.unit_id,
        )
        .order_by(model.created_at.desc(), model.id)
        .limit(limit)
        .offset(offset)
    )
    return cast(
        list[CAPAControlLinkResponse] | list[CAPAEvidenceLinkResponse],
        [_response(db, cast(TraceLink, row), parent.row_version, kind) for row in rows],
    )


@router.get("/{capa_id}/control-links", response_model=list[CAPAControlLinkResponse])
def list_control_links(
    capa_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[CAPAControlLinkResponse]:
    return cast(
        list[CAPAControlLinkResponse],
        _list(db, actor_context(db, authenticated), capa_id, "control", limit, offset),
    )


@router.get("/{capa_id}/evidence-links", response_model=list[CAPAEvidenceLinkResponse])
def list_evidence_links(
    capa_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[CAPAEvidenceLinkResponse]:
    return cast(
        list[CAPAEvidenceLinkResponse],
        _list(db, actor_context(db, authenticated), capa_id, "evidence", limit, offset),
    )


@router.post(
    "/{capa_id}/control-links",
    response_model=CAPAControlLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_control_link(
    request: Request,
    capa_id: UUID,
    body: CAPAControlLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPAControlLinkResponse:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id, body.expected_version)
    row = QMSCAPAControlLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=parent.unit_id,
        capa_id=parent.id,
        control_instance_id=body.control_instance_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        CAPAControlLinkResponse,
        _finish(
            db,
            actor,
            request.state.request_id,
            parent,
            row,
            "capa.control_linked",
            "control",
            None,
        ),
    )


@router.post(
    "/{capa_id}/evidence-links",
    response_model=CAPAEvidenceLinkResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_evidence_link(
    request: Request,
    capa_id: UUID,
    body: CAPAEvidenceLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPAEvidenceLinkResponse:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id, body.expected_version)
    row = QMSCAPAEvidenceLink(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        unit_id=parent.unit_id,
        capa_id=parent.id,
        evidence_id=body.evidence_id,
        status="active",
        row_version=1,
        created_by_user_id=actor.user_id,
        created_at=datetime.now(UTC),
        removal_reason="",
    )
    db.add(row)
    return cast(
        CAPAEvidenceLinkResponse,
        _finish(
            db,
            actor,
            request.state.request_id,
            parent,
            row,
            "capa.evidence_linked",
            "evidence",
            None,
        ),
    )


def _remove(
    request: Request,
    capa_id: UUID,
    link_id: UUID,
    body: CAPATraceLinkRemove,
    db: Session,
    authenticated: Authenticated,
    kind: Kind,
) -> CAPAControlLinkResponse | CAPAEvidenceLinkResponse:
    actor = actor_context(db, authenticated)
    parent = _parent(db, actor, capa_id, body.expected_version)
    model = QMSCAPAControlLink if kind == "control" else QMSCAPAEvidenceLink
    row = cast(
        TraceLink | None,
        db.scalar(
            select(model)
            .where(
                model.id == link_id,
                model.capa_id == parent.id,
                model.tenant_id == actor.tenant_id,
                model.unit_id == parent.unit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if row is None:
        raise HTTPException(404, "CAPA trace link not found")
    if row.status != "active" or row.row_version != body.expected_link_version:
        raise HTTPException(409, "CAPA trace link changed; refresh before removing")
    before = _values(row, parent.row_version, kind)
    row.status = "removed"
    row.removal_reason = body.reason
    row.row_version += 1
    action = f"capa.{kind}_unlinked"
    return _finish(db, actor, request.state.request_id, parent, row, action, kind, before)


@router.post(
    "/{capa_id}/control-links/{link_id}/remove",
    response_model=CAPAControlLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_control_link(
    request: Request,
    capa_id: UUID,
    link_id: UUID,
    body: CAPATraceLinkRemove,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPAControlLinkResponse:
    return cast(
        CAPAControlLinkResponse,
        _remove(request, capa_id, link_id, body, db, authenticated, "control"),
    )


@router.post(
    "/{capa_id}/evidence-links/{link_id}/remove",
    response_model=CAPAEvidenceLinkResponse,
    dependencies=[Depends(require_csrf)],
)
def remove_evidence_link(
    request: Request,
    capa_id: UUID,
    link_id: UUID,
    body: CAPATraceLinkRemove,
    db: DBSession,
    authenticated: Authenticated,
) -> CAPAEvidenceLinkResponse:
    return cast(
        CAPAEvidenceLinkResponse,
        _remove(request, capa_id, link_id, body, db, authenticated, "evidence"),
    )
