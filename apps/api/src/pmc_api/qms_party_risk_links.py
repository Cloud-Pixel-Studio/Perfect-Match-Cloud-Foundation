"""Assessed risks and opportunities cited by interested-party requirements."""

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

router = APIRouter(prefix="/context/interested-parties", tags=["qms-party-risk-links"])
SOURCE_CAPABILITY = "risks.read"


class AddRiskLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_party_version: RowVersion
    expected_risk_version: RowVersion
    requirement_id: UUID
    risk_id: UUID
    rationale: RequirementRationale


class RiskCandidate(BaseModel):
    id: UUID
    code: str
    name: str
    risk_type: Literal["risk", "opportunity"]
    state: Literal["assessed", "action_required", "monitoring"]
    row_version: int


class RiskCandidates(ScopeRead):
    items: list[RiskCandidate]
    has_more: bool


class RiskLink(BaseModel):
    id: UUID
    requirement_id: UUID
    risk_id: UUID
    requirement_snapshot: PartyRequirement
    risk_code: str
    risk_name: str
    risk_type: Literal["risk", "opportunity"]
    linked_risk_state: Literal["assessed", "action_required", "monitoring"]
    risk_version: int
    linked_party_version: int
    rationale: str
    created_at: datetime
    removed_party_version: int | None
    removed_at: datetime | None
    removal_reason: str
    requirement_current: bool
    risk_state: Literal["assessed", "action_required", "monitoring", "closed", "unavailable"]
    risk_changed: bool


class RiskLinks(ScopeRead):
    items: list[RiskLink]
    has_more: bool


@router.get("/{party_id}/risk-candidates", response_model=RiskCandidates)
def candidates(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> RiskCandidates:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, write=True, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    if INVALID_TEXT.search(q):
        raise HTTPException(422, "invalid search")
    rows = list(
        db.execute(
            text("""
SELECT risk.id,risk.code,risk.name,risk.risk_type,risk.state,risk.row_version
FROM public.qms_risks AS risk
WHERE risk.tenant_id=:tenant_id AND risk.unit_id=:unit_id
 AND risk.state IN ('assessed','action_required','monitoring')
 AND (:q='' OR strpos(lower(risk.code||' '||risk.name),lower(:q))>0)
ORDER BY risk.code,risk.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "q": q, "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    require_capability(db, "context.manage", unit_id)
    return RiskCandidates.model_validate(
        {
            **_scope(party),
            "items": rows[:limit],
            "has_more": len(rows) > limit,
        }
    )


@router.get("/{party_id}/risk-links", response_model=RiskLinks)
def links(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> RiskLinks:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    rows = list(
        db.execute(
            text("""
SELECT link.*, CASE
 WHEN risk.state IN ('assessed','action_required','monitoring','closed') THEN risk.state
 ELSE 'unavailable' END AS risk_state,
 COALESCE(risk.row_version<>link.risk_version,false) AS risk_changed
FROM public.qms_party_risk_links AS link
LEFT JOIN public.qms_risks AS risk ON risk.id=link.risk_id
 AND risk.tenant_id=link.tenant_id AND risk.unit_id=link.unit_id
WHERE link.tenant_id=:tenant_id AND link.unit_id=:unit_id AND link.party_id=:party_id
ORDER BY link.created_at DESC,link.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    requirements = {item["id"]: item for item in party.party_requirements}
    items = [
        RiskLink.model_validate(
            {
                **row,
                "requirement_current": requirements.get(str(row["requirement_id"]))
                == row["requirement_snapshot"],
            }
        )
        for row in rows[:limit]
    ]
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    return RiskLinks.model_validate(
        {
            **_scope(party),
            "items": items,
            "has_more": len(rows) > limit,
        }
    )


_ADD_RISK = text("""
INSERT INTO public.qms_party_risk_links(
 id,tenant_id,unit_id,party_id,requirement_id,risk_id,linked_party_version,risk_version,rationale
) VALUES (
 :id,:tenant_id,:unit_id,:party_id,:requirement_id,:risk_id,:new_version,:risk_version,:reason
) RETURNING id
""")
_REMOVE_RISK = text("""
UPDATE public.qms_party_risk_links SET removed_party_version=:new_version,removal_reason=:reason
WHERE id=:id AND tenant_id=:tenant_id AND unit_id=:unit_id AND party_id=:party_id
AND removed_at IS NULL RETURNING id
""")


@router.post(
    "/{party_id}/risk-links",
    response_model=LinkReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add(
    party_id: UUID,
    unit_id: UUID,
    body: AddRiskLink,
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
        source_kind="risk",
        statement=_ADD_RISK,
        source_values={
            "requirement_id": body.requirement_id,
            "risk_id": body.risk_id,
            "risk_version": body.expected_risk_version,
        },
    )


@router.post(
    "/{party_id}/risk-links/{link_id}/remove",
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
        source_kind="risk",
        statement=_REMOVE_RISK,
    )
