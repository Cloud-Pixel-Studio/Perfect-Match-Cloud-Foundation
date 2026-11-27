# ruff: noqa: E501, S608 -- fixed private SQL allowlists, values always bound.
"""Scoped supporting records. A citation observes a source; it never verifies a step."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any, Generic, Literal, TypeVar, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import (
    QMSProject,
    QMSProjectDocumentLink,
    QMSProjectEvidenceLink,
    QMSProjectStep,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability
from pmc_api.qms_projects import (
    ProjectDetail,
    Reason,
    _database_error,
    _detail,
    _locked,
    _no_store,
)


class _PrivateValidationRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def private_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                # Do not echo rationale/reasons, especially invalid UTF-8, into JSON errors.
                return JSONResponse(
                    status_code=422,
                    content={"detail": "invalid reference request"},
                    headers={"Cache-Control": "private, no-store"},
                )

        return private_handler


router = APIRouter(
    prefix="/qms-projects",
    tags=["qms-project-references"],
    dependencies=[Depends(_no_store)],
    route_class=_PrivateValidationRoute,
)
DBSession = Annotated[Session, Depends(get_db)]
Kind = Literal["document", "evidence"]
Version = Annotated[int, Field(strict=True, ge=1, le=2147483647)]


def _utf8(value: object) -> object:
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("NUL is not supported")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("valid Unicode text required") from error
    return value


ReferenceReason = Annotated[Reason, BeforeValidator(_utf8)]
Search = Annotated[str, Field(max_length=160), BeforeValidator(_utf8)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_project_version: Version
    expected_step_version: Version


class DocumentLinkInput(_Input):
    document_id: UUID
    document_revision_id: UUID
    expected_document_version: Version
    expected_revision_version: Version
    rationale: ReferenceReason


class EvidenceLinkInput(_Input):
    evidence_id: UUID
    expected_instance_version: Version
    expected_evidence_version: Version
    rationale: ReferenceReason


class LinkRemove(_Input):
    expected_link_version: Version
    reason: ReferenceReason


class LinkCommon(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    project_id: UUID
    step_id: UUID
    target_process_id: UUID
    snapshot_code: str = Field(max_length=50)
    snapshot_name: str = Field(max_length=200)
    linked_target_version: Version
    source_project_version: Version
    source_step_version: Version
    status: Literal["active", "removed"]
    row_version: Version
    rationale: ReferenceReason
    created_by_user_id: UUID
    created_at: datetime
    removed_by_user_id: UUID | None
    removed_at: datetime | None
    removal_reason: str = Field(max_length=500)


class DocumentLink(LinkCommon):
    document_id: UUID
    document_revision_id: UUID
    snapshot_revision: str = Field(max_length=40)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    linked_document_version: Version
    current_target_state: Literal["active", "changed", "superseded", "obsolete", "unavailable"]


class EvidenceLink(LinkCommon):
    evidence_id: UUID
    control_instance_id: UUID
    linked_instance_version: Version
    current_target_state: Literal["accepted", "changed", "implementation_archived", "unavailable"]


class DocumentCandidate(BaseModel):
    tenant_id: UUID
    unit_id: UUID
    document_id: UUID
    document_revision_id: UUID
    process_id: UUID
    code: str = Field(max_length=50)
    title: str = Field(max_length=200)
    revision: str = Field(max_length=40)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: Version
    revision_version: Version


class EvidenceCandidate(BaseModel):
    tenant_id: UUID
    unit_id: UUID
    evidence_id: UUID
    control_instance_id: UUID
    process_id: UUID
    code: str = Field(max_length=50)
    name: str = Field(max_length=160)
    instance_version: Version
    evidence_version: Version


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 -- OpenGrep1.29 compatibility
    tenant_id: UUID
    unit_id: UUID
    project_id: UUID
    step_id: UUID
    project_status: Literal["open", "archived"]
    project_version: Version
    step_version: Version
    observed_at: datetime
    limit: int
    offset: int
    has_more: bool
    items: list[T]


class DocumentReceipt(BaseModel):
    project: ProjectDetail
    link: DocumentLink


class EvidenceReceipt(BaseModel):
    project: ProjectDetail
    link: EvidenceLink


_TABLES: dict[Kind, type[QMSProjectDocumentLink] | type[QMSProjectEvidenceLink]] = {
    "document": QMSProjectDocumentLink,
    "evidence": QMSProjectEvidenceLink,
}
_CAPS = {"document": "documents.read", "evidence": "control_instances.read"}
# Every interpolated SQL fragment is selected from these fixed private definitions.
_CURRENT = {
    "document": """CASE WHEN d.id IS NULL OR r.id IS NULL THEN 'unavailable'
 WHEN d.status='obsolete' THEN 'obsolete' WHEN r.status='superseded' THEN 'superseded'
 WHEN d.status<>'active' OR r.status<>'active' OR r.file_state<>'clean' THEN 'unavailable'
 WHEN d.row_version<>l.linked_document_version OR r.row_version<>l.linked_target_version THEN 'changed' ELSE 'active' END""",
    "evidence": """CASE WHEN i.id IS NULL OR e.id IS NULL THEN 'unavailable'
 WHEN i.status='archived' THEN 'implementation_archived'
 WHEN e.status<>'accepted' THEN 'unavailable'
 WHEN i.row_version<>l.linked_instance_version OR e.row_version<>l.linked_target_version THEN 'changed' ELSE 'accepted' END""",
}
_JOINS = {
    "document": """LEFT JOIN public.qms_documents d ON d.id=l.document_id AND d.tenant_id=l.tenant_id AND d.unit_id=l.unit_id
 LEFT JOIN public.qms_document_revisions r ON r.id=l.document_revision_id AND r.document_id=d.id AND r.tenant_id=d.tenant_id""",
    "evidence": """LEFT JOIN public.qms_control_instance_evidence e ON e.id=l.evidence_id AND e.tenant_id=l.tenant_id AND e.unit_id=l.unit_id
 LEFT JOIN public.qms_control_instances i ON i.id=e.control_instance_id AND i.id=l.control_instance_id AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id""",
}


def _scope(
    db: Session,
    actor: OrganizationActor,
    project_id: UUID,
    step_id: UUID,
    kind: Kind,
    version: int | None = None,
) -> tuple[QMSProject, QMSProjectStep]:
    parent = (
        _locked(db, actor, project_id, version)
        if version is not None
        else db.scalar(
            select(QMSProject).where(
                QMSProject.id == project_id, QMSProject.tenant_id == actor.tenant_id
            )
        )
    )
    if parent is None:
        raise HTTPException(404, "project not found")
    require_capability(db, "projects.read", parent.unit_id)
    require_capability(db, _CAPS[kind], parent.unit_id)
    child = db.scalar(
        select(QMSProjectStep).where(
            QMSProjectStep.id == step_id,
            QMSProjectStep.project_id == parent.id,
            QMSProjectStep.tenant_id == actor.tenant_id,
            QMSProjectStep.unit_id == parent.unit_id,
        )
    )
    if child is None:
        raise HTTPException(404, "project step not found")
    if version is not None and parent.status != "open":
        raise HTTPException(409, "restore project before changing references")
    return parent, child


def _page(
    db: Session,
    actor: OrganizationActor,
    project_id: UUID,
    step_id: UUID,
    kind: Kind,
    candidates: bool,
    search: str,
    limit: int,
    offset: int,
) -> dict[str, object]:
    _scope(db, actor, project_id, step_id, kind)
    if not candidates:
        selection = f"""SELECT to_jsonb(l)||jsonb_build_object('current_target_state',{_CURRENT[kind]}) AS item
 FROM public.qms_project_{kind}_links l {_JOINS[kind]}
 WHERE l.project_id=p.id AND l.step_id=s.id AND l.tenant_id=p.tenant_id AND l.unit_id=p.unit_id
 ORDER BY (l.status='active') DESC,l.created_at DESC,l.id DESC"""
    elif kind == "document":
        selection = """SELECT jsonb_build_object('tenant_id',d.tenant_id,'unit_id',d.unit_id,'document_id',d.id,'document_revision_id',r.id,'process_id',d.process_id,'code',d.code,'title',d.title,'revision',r.revision,'file_sha256',r.file_sha256,'document_version',d.row_version,'revision_version',r.row_version) AS item
 FROM public.qms_documents d JOIN public.qms_document_revisions r ON r.document_id=d.id AND r.tenant_id=d.tenant_id
 WHERE d.tenant_id=p.tenant_id AND d.unit_id=p.unit_id AND d.status='active' AND r.status='active' AND r.file_state='clean' AND r.file_sha256 ~ '^[0-9a-f]{64}$'
 AND (:search='' OR strpos(lower(d.code||' '||d.title||' '||r.revision),lower(:search))>0)
 ORDER BY d.code,d.id,r.id"""
    else:
        selection = """SELECT jsonb_build_object('tenant_id',e.tenant_id,'unit_id',e.unit_id,'evidence_id',e.id,'control_instance_id',i.id,'process_id',i.process_id,'code',i.code,'name',e.name,'instance_version',i.row_version,'evidence_version',e.row_version) AS item
 FROM public.qms_control_instance_evidence e JOIN public.qms_control_instances i ON i.id=e.control_instance_id AND i.tenant_id=e.tenant_id AND i.unit_id=e.unit_id
 WHERE e.tenant_id=p.tenant_id AND e.unit_id=p.unit_id AND e.status='accepted' AND i.status='active'
 AND (:search='' OR strpos(lower(i.code||' '||e.name),lower(:search))>0)
 ORDER BY i.code,e.sequence,e.id"""
    record = (
        db.execute(
            text(f"""SELECT p.tenant_id,p.unit_id,p.id AS project_id,s.id AS step_id,p.status AS project_status,p.row_version AS project_version,s.row_version AS step_version,statement_timestamp() AS observed_at,
 COALESCE((SELECT jsonb_agg(q.item) FROM ({selection} LIMIT :sentinel OFFSET :offset) q),'[]'::jsonb) AS items
 FROM public.qms_projects p JOIN public.qms_project_steps s ON s.project_id=p.id AND s.tenant_id=p.tenant_id AND s.unit_id=p.unit_id
 WHERE p.id=:project AND s.id=:step AND p.tenant_id=:tenant"""),
            {
                "project": project_id,
                "step": step_id,
                "tenant": actor.tenant_id,
                "search": search,
                "sentinel": limit + 1,
                "offset": offset,
            },
        )
        .mappings()
        .first()
    )  # noqa: S608
    if record is None:
        raise HTTPException(404, "project step not found")
    data = dict(record)
    rows = data["items"]
    data.update(limit=limit, offset=offset, has_more=len(rows) > limit, items=rows[:limit])
    return data


def _link(
    db: Session, row: QMSProjectDocumentLink | QMSProjectEvidenceLink, kind: Kind
) -> DocumentLink | EvidenceLink:
    data = db.scalar(
        text(
            f"SELECT to_jsonb(l)||jsonb_build_object('current_target_state',{_CURRENT[kind]}) FROM public.qms_project_{kind}_links l {_JOINS[kind]} WHERE l.id=:id"
        ),
        {"id": row.id},
    )  # noqa: S608
    return (DocumentLink if kind == "document" else EvidenceLink).model_validate(data)


def _values(row: QMSProjectDocumentLink | QMSProjectEvidenceLink, kind: Kind) -> dict[str, object]:
    names = [
        "unit_id",
        "project_id",
        "step_id",
        "target_process_id",
        "linked_target_version",
        "source_project_version",
        "source_step_version",
        "row_version",
        "status",
    ] + (
        ["document_id", "document_revision_id", "linked_document_version"]
        if kind == "document"
        else ["evidence_id", "control_instance_id", "linked_instance_version"]
    )
    result = {
        n: str(getattr(row, n)) if isinstance(getattr(row, n), UUID) else getattr(row, n)
        for n in names
    }
    result.update(
        rationale_hash=hashlib.sha256(row.rationale.encode()).hexdigest(),
        removal_reason_hash=hashlib.sha256(row.removal_reason.encode()).hexdigest(),
    )
    return result


def _finish(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    parent: QMSProject,
    row: QMSProjectDocumentLink | QMSProjectEvidenceLink,
    kind: Kind,
    before: dict[str, object] | None,
) -> DocumentReceipt | EvidenceReceipt:
    try:
        db.execute(
            text("SELECT set_config('app.qms_project_reference_command',:command,true)"),
            {"command": "link" if before is None else "unlink"},
        )
        db.flush()
        db.refresh(row)
        db.refresh(parent)
        audit_service.record_qms_project_reference(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action=f"qms_project.{kind}_{'linked' if before is None else 'unlinked'}",
            resource_id=row.id,
            request_id=request_id,
            old_values=before,
            new_values=_values(row, kind),
        )
        project = _detail(db, parent)
        link = _link(db, row, kind)
        result = (
            DocumentReceipt(project=project, link=link)
            if isinstance(link, DocumentLink)
            else EvidenceReceipt(project=project, link=link)
        )
        db.commit()
        return result
    except DBAPIError as error:
        _database_error(db, error)
        raise AssertionError("unreachable") from error
    except Exception:
        db.rollback()
        raise


def _add(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    body: DocumentLinkInput | EvidenceLinkInput,
    db: Session,
    authenticated: Authenticated,
    kind: Kind,
) -> DocumentReceipt | EvidenceReceipt:
    actor = actor_context(db, authenticated)
    parent, child = _scope(db, actor, project_id, step_id, kind, body.expected_project_version)
    if child.row_version != body.expected_step_version:
        raise HTTPException(409, "step changed; refresh references")
    values = {
        "id": uuid4(),
        "tenant_id": actor.tenant_id,
        "unit_id": parent.unit_id,
        "project_id": parent.id,
        "step_id": child.id,
        "source_project_version": body.expected_project_version + 1,
        "source_step_version": body.expected_step_version + 1,
        "rationale": body.rationale,
        "status": "active",
        "row_version": 1,
        "created_by_user_id": actor.user_id,
        "created_at": datetime.now(UTC),
        "removal_reason": "",
    }
    if isinstance(body, DocumentLinkInput):
        row: QMSProjectDocumentLink | QMSProjectEvidenceLink = QMSProjectDocumentLink(
            **values,
            document_id=body.document_id,
            document_revision_id=body.document_revision_id,
            linked_document_version=body.expected_document_version,
            linked_target_version=body.expected_revision_version,
        )
    else:
        row = QMSProjectEvidenceLink(
            **values,
            evidence_id=body.evidence_id,
            linked_instance_version=body.expected_instance_version,
            linked_target_version=body.expected_evidence_version,
        )
    db.add(row)
    return _finish(db, actor, request.state.request_id, parent, row, kind, None)


def _remove(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    link_id: UUID,
    body: LinkRemove,
    db: Session,
    authenticated: Authenticated,
    kind: Kind,
) -> DocumentReceipt | EvidenceReceipt:
    actor = actor_context(db, authenticated)
    parent, child = _scope(db, actor, project_id, step_id, kind, body.expected_project_version)
    if child.row_version != body.expected_step_version:
        raise HTTPException(409, "step changed; refresh references")
    model = _TABLES[kind]
    row = cast(
        QMSProjectDocumentLink | QMSProjectEvidenceLink | None,
        db.scalar(
            select(model)
            .where(
                model.id == link_id,
                model.project_id == parent.id,
                model.step_id == child.id,
                model.tenant_id == actor.tenant_id,
                model.unit_id == parent.unit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if row is None:
        raise HTTPException(404, "reference not found")
    if row.status != "active" or row.row_version != body.expected_link_version:
        raise HTTPException(409, "reference changed; refresh before removal")
    before = _values(row, kind)
    row.status, row.removal_reason, row.row_version = "removed", body.reason, row.row_version + 1
    row.source_project_version, row.source_step_version = (
        body.expected_project_version + 1,
        body.expected_step_version + 1,
    )
    return _finish(db, actor, request.state.request_id, parent, row, kind, before)


@router.get("/{project_id}/steps/{step_id}/document-links", response_model=Page[DocumentLink])
def document_links(
    project_id: UUID,
    step_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict[str, object]:
    actor = actor_context(db, authenticated)
    return _page(db, actor, project_id, step_id, "document", False, "", limit, offset)


@router.get(
    "/{project_id}/steps/{step_id}/document-candidates", response_model=Page[DocumentCandidate]
)
def document_candidates(
    project_id: UUID,
    step_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    search: Search = "",
) -> dict[str, object]:
    actor = actor_context(db, authenticated)
    return _page(db, actor, project_id, step_id, "document", True, search, limit, offset)


@router.post(
    "/{project_id}/steps/{step_id}/document-links",
    response_model=DocumentReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_document_link(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    body: DocumentLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentReceipt | EvidenceReceipt:
    return _add(request, project_id, step_id, body, db, authenticated, "document")


@router.post(
    "/{project_id}/steps/{step_id}/document-links/{link_id}/remove",
    response_model=DocumentReceipt,
    dependencies=[Depends(require_csrf)],
)
def remove_document_link(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    link_id: UUID,
    body: LinkRemove,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentReceipt | EvidenceReceipt:
    return _remove(request, project_id, step_id, link_id, body, db, authenticated, "document")


@router.get("/{project_id}/steps/{step_id}/evidence-links", response_model=Page[EvidenceLink])
def evidence_links(
    project_id: UUID,
    step_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict[str, object]:
    actor = actor_context(db, authenticated)
    return _page(db, actor, project_id, step_id, "evidence", False, "", limit, offset)


@router.get(
    "/{project_id}/steps/{step_id}/evidence-candidates", response_model=Page[EvidenceCandidate]
)
def evidence_candidates(
    project_id: UUID,
    step_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    search: Search = "",
) -> dict[str, object]:
    actor = actor_context(db, authenticated)
    return _page(db, actor, project_id, step_id, "evidence", True, search, limit, offset)


@router.post(
    "/{project_id}/steps/{step_id}/evidence-links",
    response_model=EvidenceReceipt,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_evidence_link(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    body: EvidenceLinkInput,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentReceipt | EvidenceReceipt:
    return _add(request, project_id, step_id, body, db, authenticated, "evidence")


@router.post(
    "/{project_id}/steps/{step_id}/evidence-links/{link_id}/remove",
    response_model=EvidenceReceipt,
    dependencies=[Depends(require_csrf)],
)
def remove_evidence_link(
    request: Request,
    project_id: UUID,
    step_id: UUID,
    link_id: UUID,
    body: LinkRemove,
    db: DBSession,
    authenticated: Authenticated,
) -> DocumentReceipt | EvidenceReceipt:
    return _remove(request, project_id, step_id, link_id, body, db, authenticated, "evidence")
