"""Approved document revisions cited by interested-party requirements."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
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

router = APIRouter(prefix="/context/interested-parties", tags=["qms-party-document-links"])
SOURCE_CAPABILITY = "documents.read"


class AddDocumentLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_party_version: RowVersion
    expected_document_version: RowVersion
    expected_revision_version: RowVersion
    requirement_id: UUID
    document_id: UUID
    document_revision_id: UUID
    rationale: RequirementRationale


class DocumentCandidate(BaseModel):
    id: UUID
    document_id: UUID
    code: str
    name: str
    revision: str
    row_version: int
    document_version: int


class DocumentCandidates(ScopeRead):
    items: list[DocumentCandidate]
    has_more: bool


class DocumentLink(BaseModel):
    id: UUID
    requirement_id: UUID
    document_id: UUID
    document_revision_id: UUID
    requirement_snapshot: PartyRequirement
    document_code: str
    document_title: str
    revision: str
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: int
    revision_version: int
    linked_party_version: int
    rationale: str
    created_at: datetime
    removed_party_version: int | None
    removed_at: datetime | None
    removal_reason: str
    requirement_current: bool
    document_state: Literal["current", "changed", "obsolete", "superseded", "unavailable"]


class DocumentLinks(ScopeRead):
    items: list[DocumentLink]
    has_more: bool


@router.get("/{party_id}/document-candidates", response_model=DocumentCandidates)
def candidates(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> DocumentCandidates:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, write=True, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    if INVALID_TEXT.search(q):
        raise HTTPException(422, "invalid search")
    rows = list(
        db.execute(
            text("""
SELECT r.id,d.id AS document_id,d.code,d.title AS name,r.revision,r.row_version,
 d.row_version AS document_version
FROM public.qms_documents AS d JOIN public.qms_document_revisions AS r
 ON r.document_id=d.id AND r.tenant_id=d.tenant_id AND r.id=d.current_revision_id
WHERE d.tenant_id=:tenant_id AND d.unit_id=:unit_id AND d.status='active'
 AND r.status='active' AND r.file_state='clean' AND r.file_sha256 ~ '^[0-9a-f]{64}$'
 AND (:q='' OR strpos(lower(d.code||' '||d.title||' '||r.revision),lower(:q))>0)
ORDER BY d.code,r.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "q": q, "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    require_capability(db, "context.manage", unit_id)
    return DocumentCandidates.model_validate(
        {
            **_scope(party),
            "items": rows[:limit],
            "has_more": len(rows) > limit,
        }
    )


@router.get("/{party_id}/document-links", response_model=DocumentLinks)
def links(
    party_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> DocumentLinks:
    actor = actor_context(db, authenticated)
    _authority(db, unit_id, source=SOURCE_CAPABILITY)
    party = _find(db, actor, "interested-parties", unit_id, party_id)
    rows = list(
        db.execute(
            text("""
SELECT link.*, CASE
 WHEN d.id IS NULL OR r.id IS NULL THEN 'unavailable'
 WHEN d.status='obsolete' THEN 'obsolete'
 WHEN r.status='superseded' THEN 'superseded'
 WHEN d.status<>'active' OR r.status<>'active' OR r.file_state<>'clean'
   OR d.current_revision_id IS DISTINCT FROM r.id THEN 'unavailable'
 WHEN d.row_version<>link.document_version OR r.row_version<>link.revision_version
   OR r.file_sha256 IS DISTINCT FROM link.file_sha256 THEN 'changed'
 ELSE 'current' END AS document_state
FROM public.qms_party_document_links AS link
LEFT JOIN public.qms_documents AS d ON d.id=link.document_id
 AND d.tenant_id=link.tenant_id AND d.unit_id=link.unit_id
LEFT JOIN public.qms_document_revisions AS r ON r.id=link.document_revision_id
 AND r.document_id=d.id AND r.tenant_id=d.tenant_id
WHERE link.tenant_id=:tenant_id AND link.unit_id=:unit_id AND link.party_id=:party_id
ORDER BY link.created_at DESC,link.id LIMIT :limit OFFSET :offset
"""),
            {**_scope(party), "limit": limit + 1, "offset": offset},
        ).mappings()
    )
    requirements = {item["id"]: item for item in party.party_requirements}
    items = [
        DocumentLink.model_validate(
            {
                **row,
                "requirement_current": requirements.get(str(row["requirement_id"]))
                == row["requirement_snapshot"],
            }
        )
        for row in rows[:limit]
    ]
    _finish_read(db, authenticated, actor, party, response, source=SOURCE_CAPABILITY)
    return DocumentLinks.model_validate(
        {
            **_scope(party),
            "items": items,
            "has_more": len(rows) > limit,
        }
    )


_ADD_DOCUMENT = text("""
INSERT INTO public.qms_party_document_links(
 id,tenant_id,unit_id,party_id,requirement_id,document_id,document_revision_id,
 linked_party_version,document_version,revision_version,rationale
) VALUES (
 :id,:tenant_id,:unit_id,:party_id,:requirement_id,:document_id,:document_revision_id,
 :new_version,:document_version,:revision_version,:reason
) RETURNING id
""")
_REMOVE_DOCUMENT = text("""
UPDATE public.qms_party_document_links SET removed_party_version=:new_version,removal_reason=:reason
WHERE id=:id AND tenant_id=:tenant_id AND unit_id=:unit_id AND party_id=:party_id
AND removed_at IS NULL RETURNING id
""")


@router.post(
    "/{party_id}/document-links",
    response_model=LinkReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add(
    party_id: UUID,
    unit_id: UUID,
    body: AddDocumentLink,
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
        source_kind="document",
        statement=_ADD_DOCUMENT,
        source_values={
            "requirement_id": body.requirement_id,
            "document_id": body.document_id,
            "document_revision_id": body.document_revision_id,
            "document_version": body.expected_document_version,
            "revision_version": body.expected_revision_version,
        },
    )


@router.post(
    "/{party_id}/document-links/{link_id}/remove",
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
        source_kind="document",
        statement=_REMOVE_DOCUMENT,
    )
