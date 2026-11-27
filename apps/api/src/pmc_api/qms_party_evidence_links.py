"""Accepted control evidence cited by interested-party requirements."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from pmc_api.auth import Authenticated, require_csrf
from pmc_api.qms_access import actor_context, require_capability
from pmc_api.qms_context import (
    INVALID_TEXT,
    DBSession,
    PartyRequirement,
    RequirementRationale,
    RowVersion,
    _find,
)
from pmc_api.qms_party_process_links import (
    LinkReceipt,
    RemoveProcessLink,
    ScopeRead,
    _authority,
    _finish_read,
    _scope,
    write_party_link,
)

router = APIRouter(prefix="/context/interested-parties", tags=["qms-party-evidence-links"])
SOURCE_CAPABILITY = "control_instances.read"


class AddEvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_party_version: RowVersion
    expected_instance_version: RowVersion
    expected_evidence_version: RowVersion
    requirement_id: UUID
    control_instance_id: UUID
    evidence_id: UUID
    rationale: RequirementRationale


class EvidenceCandidate(BaseModel):
    id: UUID
    control_instance_id: UUID
    code: str
    name: str
    evidence_type: str
    row_version: int
    instance_version: int


class EvidenceCandidates(ScopeRead):
    items: list[EvidenceCandidate]
    has_more: bool


class EvidenceLink(BaseModel):
    id: UUID
    requirement_id: UUID
    control_instance_id: UUID
    evidence_id: UUID
    requirement_snapshot: PartyRequirement
    control_code: str
    evidence_name: str
    evidence_type: str
    accepted_at: datetime
    instance_version: int
    evidence_version: int
    linked_party_version: int
    rationale: str
    created_at: datetime
    removed_party_version: int | None
    removed_at: datetime | None
    removal_reason: str
    requirement_current: bool
    evidence_state: Literal["current", "changed", "implementation_archived", "unavailable"]


class EvidenceLinks(ScopeRead):
    items: list[EvidenceLink]
    has_more: bool


@router.get("/{party_id}/evidence-candidates", response_model=EvidenceCandidates)
def candidates(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> EvidenceCandidates:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, write=True, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    if INVALID_TEXT.search(q):
        raise HTTPException(422, "invalid search")
    rows = list(
        db.execute(
            text("""
SELECT e.id,i.id AS control_instance_id,i.code,e.name,e.evidence_type,e.row_version,
 i.row_version AS instance_version
FROM public.qms_control_instance_evidence AS e JOIN public.qms_control_instances AS i
 ON i.id=e.control_instance_id AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id
WHERE e.tenant_id=:tenant_id AND e.unit_id=:unit_id AND i.status='active' AND e.status='accepted'
 AND (:q='' OR strpos(lower(i.code||' '||e.name),lower(:q))>0)
ORDER BY i.code,e.sequence,e.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "q": q, "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    require_capability(db, "context.manage", unit_id)
    return EvidenceCandidates.model_validate(
        {
            **_scope(party),
            "items": rows[:limit],
            "has_more": len(rows) > limit,
        }
    )


@router.get("/{party_id}/evidence-links", response_model=EvidenceLinks)
def links(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> EvidenceLinks:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    rows = list(
        db.execute(
            text("""
SELECT link.*, CASE
 WHEN i.id IS NULL OR e.id IS NULL THEN 'unavailable'
 WHEN i.status='archived' THEN 'implementation_archived'
 WHEN i.status<>'active' OR e.status<>'accepted' THEN 'unavailable'
 WHEN i.row_version<>link.instance_version OR e.row_version<>link.evidence_version THEN 'changed'
 ELSE 'current' END AS evidence_state
FROM public.qms_party_evidence_links AS link
LEFT JOIN public.qms_control_instances AS i ON i.id=link.control_instance_id
 AND i.tenant_id=link.tenant_id AND i.unit_id=link.unit_id
LEFT JOIN public.qms_control_instance_evidence AS e ON e.id=link.evidence_id
 AND e.control_instance_id=i.id AND e.tenant_id=link.tenant_id AND e.unit_id=link.unit_id
WHERE link.tenant_id=:tenant_id AND link.unit_id=:unit_id AND link.party_id=:party_id
ORDER BY link.created_at DESC,link.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    requirements = {item["id"]: item for item in party.party_requirements}
    items = [
        EvidenceLink.model_validate(
            {
                **row,
                "requirement_current": requirements.get(str(row["requirement_id"]))
                == row["requirement_snapshot"],
            }
        )
        for row in rows[:limit]
    ]
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    return EvidenceLinks.model_validate(
        {
            **_scope(party),
            "items": items,
            "has_more": len(rows) > limit,
        }
    )


_ADD_EVIDENCE = text("""
INSERT INTO public.qms_party_evidence_links(
 id,tenant_id,unit_id,party_id,requirement_id,control_instance_id,evidence_id,
 linked_party_version,instance_version,evidence_version,rationale
) VALUES (
 :id,:tenant_id,:unit_id,:party_id,:requirement_id,:control_instance_id,:evidence_id,
 :new_version,:instance_version,:evidence_version,:reason
) RETURNING id
""")
_REMOVE_EVIDENCE = text("""
UPDATE public.qms_party_evidence_links SET removed_party_version=:new_version,removal_reason=:reason
WHERE id=:id AND tenant_id=:tenant_id AND unit_id=:unit_id AND party_id=:party_id
AND removed_at IS NULL RETURNING id
""")


@router.post(
    "/{party_id}/evidence-links",
    response_model=LinkReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add(
    party_id: UUID,
    unit_id: UUID,
    body: AddEvidenceLink,
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
        source_kind="evidence",
        statement=_ADD_EVIDENCE,
        source_values={
            "requirement_id": body.requirement_id,
            "control_instance_id": body.control_instance_id,
            "evidence_id": body.evidence_id,
            "instance_version": body.expected_instance_version,
            "evidence_version": body.expected_evidence_version,
        },
    )


@router.post(
    "/{party_id}/evidence-links/{link_id}/remove",
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
        source_kind="evidence",
        statement=_REMOVE_EVIDENCE,
    )
