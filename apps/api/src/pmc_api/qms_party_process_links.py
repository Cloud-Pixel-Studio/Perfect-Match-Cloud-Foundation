"""Process references with separate access from the parent register."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from pmc_api.auth import Authenticated, require_csrf
from pmc_api.models import QMSContextRecord, QMSProcess
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability
from pmc_api.qms_context import (
    INVALID_TEXT,
    DBSession,
    PartyRequirement,
    RequirementRationale,
    RowVersion,
    _audit_values,
    _database_error,
    _find,
    _headers,
    _persist,
    _set_command,
    _verify,
)

router = APIRouter(prefix="/context/interested-parties", tags=["qms-party-process-links"])


class AddProcessLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_party_version: RowVersion
    expected_process_version: RowVersion
    requirement_id: UUID
    process_id: UUID
    rationale: RequirementRationale


class RemoveProcessLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_party_version: RowVersion
    reason: RequirementRationale


class ScopeRead(BaseModel):
    tenant_id: UUID
    unit_id: UUID
    party_id: UUID
    party_version: int


class ProcessCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    row_version: int


class ProcessCandidates(ScopeRead):
    items: list[ProcessCandidate]
    has_more: bool


class ProcessLink(BaseModel):
    id: UUID
    requirement_id: UUID
    process_id: UUID
    requirement_snapshot: PartyRequirement
    process_code: str
    process_name: str
    process_version: int
    linked_party_version: int
    rationale: str
    created_at: datetime
    removed_party_version: int | None
    removed_at: datetime | None
    removal_reason: str
    requirement_current: bool
    process_state: Literal["current", "changed", "archived", "unavailable"]


class ProcessLinks(ScopeRead):
    items: list[ProcessLink]
    has_more: bool


class LinkReceipt(ScopeRead):
    link_id: UUID
    action: Literal["linked", "removed"]


def _scope(party: QMSContextRecord) -> dict[str, UUID | int]:
    return {
        "tenant_id": party.tenant_id,
        "unit_id": party.unit_id,
        "party_id": party.id,
        "party_version": party.row_version,
    }


def _authority(
    db: Session, unit: UUID, *, write: bool = False, source: str = "processes.read"
) -> None:
    require_capability(db, "context.read", unit)
    require_capability(db, source, unit)
    if write:
        require_capability(db, "context.manage", unit)


def _finish_read(
    db: Session,
    auth: Authenticated,
    actor: OrganizationActor,
    party: QMSContextRecord,
    response: Response,
    *,
    source: str = "processes.read",
) -> None:
    _verify(db, auth, actor, party.unit_id, "context.read")
    require_capability(db, source, party.unit_id)
    version = db.scalar(
        select(QMSContextRecord.row_version).where(
            QMSContextRecord.id == party.id,
            QMSContextRecord.tenant_id == actor.tenant_id,
            QMSContextRecord.unit_id == party.unit_id,
        )
    )
    if version != party.row_version:
        raise HTTPException(409, "party changed; refresh links")
    _headers(response, actor)


@router.get("/{party_id}/process-candidates", response_model=ProcessCandidates)
def candidates(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> ProcessCandidates:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, write=True)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    if INVALID_TEXT.search(q):
        raise HTTPException(422, "invalid search")
    statement = select(QMSProcess).where(
        QMSProcess.tenant_id == actor.tenant_id,
        QMSProcess.unit_id == unit_id,
        QMSProcess.status == "active",
    )
    if q:
        statement = statement.where(
            QMSProcess.code.icontains(q, autoescape=True)
            | QMSProcess.name.icontains(q, autoescape=True)
        )
    rows = list(
        db.scalars(
            statement.order_by(QMSProcess.code, QMSProcess.id).limit(limit + 1).offset(offset)
        )
    )
    _finish_read(db, authenticated, actor, party, response)
    require_capability(db, "context.manage", unit_id)
    return ProcessCandidates.model_validate(
        {
            **_scope(party),
            "items": rows[:limit],
            "has_more": len(rows) > limit,
        }
    )


@router.get("/{party_id}/process-links", response_model=ProcessLinks)
def links(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> ProcessLinks:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    # Include withdrawn and superseded links. Readers still need current source authority.
    rows = list(
        db.execute(
            text("""
SELECT link.*, CASE
 WHEN process.id IS NULL THEN 'unavailable'
 WHEN process.status='archived' THEN 'archived'
 WHEN process.row_version<>link.process_version THEN 'changed'
 ELSE 'current' END AS process_state
FROM public.qms_party_process_links AS link
LEFT JOIN public.qms_processes AS process ON process.id=link.process_id
 AND process.tenant_id=link.tenant_id AND process.unit_id=link.unit_id
WHERE link.tenant_id=:tenant_id AND link.unit_id=:unit_id AND link.party_id=:party_id
ORDER BY link.created_at DESC,link.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    requirements = {item["id"]: item for item in party.party_requirements}
    items = [
        ProcessLink.model_validate(
            {
                **row,
                "requirement_current": requirements.get(str(row["requirement_id"]))
                == row["requirement_snapshot"],
            }
        )
        for row in rows[:limit]
    ]
    _finish_read(db, authenticated, actor, party, response)
    return ProcessLinks.model_validate(
        {
            **_scope(party),
            "items": items,
            "has_more": len(rows) > limit,
        }
    )


def write_party_link(
    party_id: UUID,
    unit_id: UUID,
    link_id: UUID,
    db: Session,
    auth: Authenticated,
    request: Request,
    response: Response,
    *,
    expected_version: int,
    reason: str,
    operation: Literal["link", "remove"],
    source_kind: Literal["process", "document", "evidence", "risk"],
    statement: TextClause,
    source_values: dict[str, object] | None = None,
) -> LinkReceipt:
    actor = actor_context(db, auth)
    source_capability = {
        "process": "processes.read",
        "document": "documents.read",
        "evidence": "control_instances.read",
        "risk": "risks.read",
    }[source_kind]
    _authority(db, unit_id, write=True, source=source_capability)
    if not reason or INVALID_TEXT.search(reason):
        raise HTTPException(422, "a valid rationale is required")
    try:
        # Always lock the parent before changing a link. Parent edits use the same lock.
        party = _find(db, actor, "interested-parties", unit_id, party_id, lock=True)
        if party.row_version != expected_version or party.status == "retired":
            raise HTTPException(409, "party changed or was retired; refresh before editing links")
        before = _audit_values(party)
        _set_command(db, "updated")
        db.execute(
            text("SELECT set_config(:setting,:command,true)"),
            {"setting": f"app.qms_party_{source_kind}_command", "command": operation},
        )
        parameters = {
            **_scope(party),
            "id": link_id,
            "new_version": party.row_version + 1,
            "reason": reason,
            **(source_values or {}),
        }
        if db.scalar(statement, parameters) is None:
            raise HTTPException(404, "active link not found")
        snapshot = _persist(
            db,
            actor,
            auth,
            request,
            party,
            "updated",
            before,
            source_capability=source_capability,
        )
    except DBAPIError as error:
        db.rollback()
        _database_error(error)
    _headers(response, actor)
    return LinkReceipt(
        tenant_id=actor.tenant_id,
        unit_id=unit_id,
        party_id=party_id,
        party_version=snapshot.row_version,
        link_id=link_id,
        action="linked" if operation == "link" else "removed",
    )


_ADD_PROCESS = text("""
INSERT INTO public.qms_party_process_links(
 id,tenant_id,unit_id,party_id,requirement_id,process_id,
 linked_party_version,process_version,rationale
) VALUES (
 :id,:tenant_id,:unit_id,:party_id,:requirement_id,:process_id,:new_version,:process_version,:reason
) RETURNING id
""")
_REMOVE_PROCESS = text("""
UPDATE public.qms_party_process_links SET removed_party_version=:new_version,removal_reason=:reason
WHERE id=:id AND tenant_id=:tenant_id AND unit_id=:unit_id AND party_id=:party_id
AND removed_at IS NULL RETURNING id
""")


@router.post(
    "/{party_id}/process-links",
    response_model=LinkReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add(
    party_id: UUID,
    unit_id: UUID,
    body: AddProcessLink,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> LinkReceipt:
    return write_party_link(
        party_id,
        unit_id,
        uuid4(),
        db,
        authenticated,
        request,
        response,
        expected_version=body.expected_party_version,
        reason=body.rationale,
        operation="link",
        source_kind="process",
        statement=_ADD_PROCESS,
        source_values={
            "requirement_id": body.requirement_id,
            "process_id": body.process_id,
            "process_version": body.expected_process_version,
        },
    )


@router.post(
    "/{party_id}/process-links/{link_id}/remove",
    response_model=LinkReceipt,
    dependencies=[Depends(require_csrf)],
)
def remove(
    party_id: UUID,
    unit_id: UUID,
    link_id: UUID,
    body: RemoveProcessLink,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> LinkReceipt:
    return write_party_link(
        party_id,
        unit_id,
        link_id,
        db,
        authenticated,
        request,
        response,
        expected_version=body.expected_party_version,
        reason=body.reason,
        operation="remove",
        source_kind="process",
        statement=_REMOVE_PROCESS,
    )
