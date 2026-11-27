"""Context register with scoped access and independent review."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal, Never
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from sqlalchemy import bindparam, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db, set_request_context
from pmc_api.models import ApplicationSession, QMSContextRecord, QMSContextRevision
from pmc_api.organization_service import OrganizationActor, require_context
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/context", tags=["qms-context"])
DBSession = Annotated[Session, Depends(get_db)]
Kind = Literal["issues", "interested-parties", "qms-scope"]
State = Literal["draft", "active", "retired"]
Command = Literal["created", "updated", "reviewed", "retired"]
Relevance = Literal["relevant", "not_relevant", "under_review"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Decision = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
RowVersion = Annotated[int, Field(strict=True, ge=1, lt=2147483647)]
CATEGORIES = frozenset(
    {
        "legal",
        "regulatory",
        "technology",
        "market",
        "culture",
        "social",
        "economic",
        "environmental",
        "strategic",
        "other",
    }
)
PARTIES = frozenset(
    {"customer", "employee", "supplier", "regulator", "owner", "community", "other"}
)
INVALID_TEXT = re.compile(r"[\x00\ud800-\udfff]")
RequirementDisposition = Literal["pending", "addressed_by_qms", "outside_qms"]
REQUIREMENT_TEXT_EDGES = re.compile(r"^[\s\ufeff]+|[\s\ufeff]+$")


def _trim_requirement_text(value: object) -> object:
    return REQUIREMENT_TEXT_EDGES.sub("", value) if isinstance(value, str) else value


RequirementRationale = Annotated[
    str, StringConstraints(max_length=600), BeforeValidator(_trim_requirement_text)
]


class PartyRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    statement: Annotated[
        str,
        StringConstraints(min_length=1, max_length=360),
        BeforeValidator(_trim_requirement_text),
    ]
    source: Annotated[
        str,
        StringConstraints(min_length=1, max_length=200),
        BeforeValidator(_trim_requirement_text),
    ]
    disposition: RequirementDisposition
    rationale: RequirementRationale = ""

    @model_validator(mode="after")
    def validate_content(self) -> PartyRequirement:
        if any(
            INVALID_TEXT.search(value) for value in (self.statement, self.source, self.rationale)
        ):
            raise ValueError("requirement contains unsupported characters")
        if self.disposition != "pending" and not self.rationale:
            raise ValueError("a decided requirement needs a rationale")
        return self


class RequirementAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    party_requirements: list[PartyRequirement] = Field(default_factory=list, max_length=20)
    no_requirements_reason: RequirementRationale = ""


ScopeText = Annotated[
    str, StringConstraints(max_length=4000), BeforeValidator(_trim_requirement_text)
]


class ScopeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    products_services: ScopeText
    basis: ScopeText
    applicability: Literal["undecided", "all_applicable", "exceptions"]
    non_applicability: ScopeText

    @model_validator(mode="after")
    def validate_content(self) -> ScopeDefinition:
        if any(
            INVALID_TEXT.search(value)
            for value in (self.products_services, self.basis, self.non_applicability)
        ):
            raise ValueError("scope definition contains unsupported characters")
        if self.applicability != "exceptions" and self.non_applicability:
            raise ValueError("justification is only valid for requirements that do not apply")
        return self

    def ready(self) -> bool:
        return bool(
            self.products_services
            and self.basis
            and self.applicability != "undecided"
            and (self.applicability != "exceptions" or self.non_applicability)
        )


class RecordFields(RequirementAssessment):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: Code
    name: Label
    classification: Label
    category: str = Field("", max_length=20)
    relevance: Relevance
    description: Description
    requirements: Notes = ""
    evidence_summary: Notes = ""
    scope_definition: ScopeDefinition | None = None
    owner_user_id: UUID
    review_due_on: date


class RecordCreate(RecordFields):
    unit_id: UUID


class RecordEdit(RecordFields):
    expected_version: RowVersion


class Retire(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: RowVersion
    note: Decision


class Review(Retire):
    review_due_on: date


class RecordRead(RecordFields):
    model_config = ConfigDict(from_attributes=True)
    owner_display_name: str | None = None
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    kind: Kind
    status: State
    row_version: int
    created_by_user_id: UUID
    content_editor_user_id: UUID
    updated_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    decision_note: str


class RecordRevision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    command: Command
    snapshot: RecordRead


class ResponsiblePerson(BaseModel):
    user_id: UUID
    display_name: str


def _validate_content(kind: Kind, body: RecordFields) -> None:
    if kind == "issues":
        valid = body.classification in {"internal", "external"} and body.category in CATEGORIES
    elif kind == "qms-scope":
        valid = (
            body.code == "QMS-SCOPE"
            and body.classification == "declared_scope"
            and body.category == ""
            and body.relevance == "relevant"
            and not (body.requirements or body.evidence_summary)
            and bool(_trim_requirement_text(body.description))
            and body.scope_definition is not None
        )
    else:
        valid = body.classification in PARTIES and body.category == ""
    if kind != "qms-scope" and body.scope_definition is not None:
        valid = False
    if not valid or any(
        INVALID_TEXT.search(value) for value in body.model_dump().values() if isinstance(value, str)
    ):
        raise HTTPException(422, "invalid context record fields")


def _requirement_values(
    kind: Kind, body: RecordFields, row: QMSContextRecord | None = None
) -> tuple[list[dict[str, str]], str]:
    # An earlier client can still use the PATCH contract without erasing the assessment.
    supplied = body.model_fields_set
    entries = (
        [item.model_dump(mode="json") for item in body.party_requirements]
        if row is None or "party_requirements" in supplied
        else row.party_requirements
    )
    reason = (
        body.no_requirements_reason
        if row is None or "no_requirements_reason" in supplied
        else row.no_requirements_reason
    )
    if kind != "interested-parties" and (entries or reason):
        raise HTTPException(422, "only interested parties have a requirement assessment")
    if entries and reason:
        raise HTTPException(422, "record either individual requirements or a reason for none")
    if len({entry["id"] for entry in entries}) != len(entries):
        raise HTTPException(422, "requirement IDs must be unique within the interested party")
    return entries, reason


def _require_reviewable_party(row: QMSContextRecord) -> None:
    if row.kind != "interested-parties":
        return
    if not row.party_requirements and not row.no_requirements_reason:
        raise HTTPException(409, "record the requirements assessment before review")
    dispositions = {item["disposition"] for item in row.party_requirements}
    if "pending" in dispositions:
        raise HTTPException(409, "decide which requirements the QMS will address before review")
    if row.relevance == "not_relevant" and "addressed_by_qms" in dispositions:
        raise HTTPException(409, "requirements addressed by the QMS require a relevant party")


def _headers(response: Response, actor: OrganizationActor) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Tenant-ID"] = str(actor.tenant_id)


def _verify(
    db: Session, auth: Authenticated, actor: OrganizationActor, unit: UUID, authority: str
) -> None:
    set_request_context(
        db, user_id=actor.user_id, tenant_id=actor.tenant_id, session_hash=auth.record.token_hash
    )
    session = db.scalar(
        select(ApplicationSession)
        .where(ApplicationSession.id == auth.record.id)
        .execution_options(populate_existing=True)
    )
    if session is None or session.revoked_at or session.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "session expired or invalid")
    if session.current_tenant_id != actor.tenant_id or session.user_id != actor.user_id:
        raise HTTPException(409, "workspace changed; refresh the register")
    current = require_context(db, user_id=actor.user_id, tenant_id=actor.tenant_id)
    if current.role != actor.role:
        raise HTTPException(403, "workspace access changed")
    require_capability(db, "context.read", unit)
    if authority != "context.read":
        require_capability(db, authority, unit)


def _criteria(actor: OrganizationActor, kind: Kind, unit: UUID) -> tuple[ColumnElement[bool], ...]:
    return (
        QMSContextRecord.tenant_id == actor.tenant_id,
        QMSContextRecord.unit_id == unit,
        QMSContextRecord.kind == kind,
    )


def _find(
    db: Session,
    actor: OrganizationActor,
    kind: Kind,
    unit: UUID,
    record_id: UUID,
    *,
    lock: bool = False,
) -> QMSContextRecord:
    query = select(QMSContextRecord).where(
        *_criteria(actor, kind, unit), QMSContextRecord.id == record_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "context record not found")
    return row


def _audit_values(entry: QMSContextRecord) -> dict[str, object]:
    return {
        "unit_id": str(entry.unit_id),
        "kind": entry.kind,
        "status": entry.status,
        "row_version": entry.row_version,
    }


def _read_records(db: Session, rows: list[QMSContextRecord]) -> list[RecordRead]:
    if not rows:
        return []
    lookup = text(
        "SELECT user_id,display_name FROM public.organization_member_directory() "
        "WHERE user_id IN :users"
    ).bindparams(bindparam("users", expanding=True))
    owners = {
        row.user_id: row.display_name
        for row in db.execute(lookup, {"users": list({row.owner_user_id for row in rows})})
    }
    results = [RecordRead.model_validate(row) for row in rows]
    for result in results:
        result.owner_display_name = owners.get(result.owner_user_id)
    return results


def _set_command(db: Session, command: Command) -> None:
    db.execute(
        text("SELECT set_config('app.qms_context_command',:command,true)"), {"command": command}
    )


def _database_error(error: DBAPIError) -> Never:
    original = error.orig
    details = original.args[0] if original is not None and original.args else None
    state = details.get("C") if isinstance(details, dict) else getattr(original, "sqlstate", None)
    if state in {"23503", "23505", "23514", "40001", "40P01", "55P03"}:
        raise HTTPException(
            409, "context code, responsible person, review or version conflicts"
        ) from None
    if state == "42501":
        raise HTTPException(403, "context authority denied") from None
    raise error


def _persist(
    db: Session,
    actor: OrganizationActor,
    auth: Authenticated,
    request: Request,
    row: QMSContextRecord,
    command: Command,
    before: dict[str, object] | None = None,
    *,
    source_capability: str | None = None,
) -> RecordRead:
    _set_command(db, command)
    db.flush()
    db.refresh(row)
    audit_service.record_qms_context(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=f"qms_context.{command}",
        resource_id=row.id,
        request_id=request.state.request_id,
        old_values=before,
        new_values=_audit_values(row),
    )
    db.flush()
    result = _read_records(db, [row])[0]
    authority = "context.review" if command == "reviewed" else "context.manage"
    _verify(db, auth, actor, row.unit_id, authority)
    if source_capability:
        require_capability(db, source_capability, row.unit_id)
    db.commit()
    return result


@router.get("/members", response_model=list[ResponsiblePerson])
def responsible_people(
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> list[ResponsiblePerson]:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", unit_id)
    require_capability(db, "context.manage", unit_id)
    rows = db.execute(
        text(
            "SELECT user_id,display_name FROM public.organization_member_directory() "
            "ORDER BY lower(display_name),user_id LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    ).mappings()
    result = [ResponsiblePerson.model_validate(row) for row in rows]
    _verify(db, authenticated, actor, unit_id, "context.manage")
    _headers(response, actor)
    return result


@router.get("/{kind}", response_model=list[RecordRead])
def records(
    kind: Kind,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    status: State | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> list[RecordRead]:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", unit_id)
    query = select(QMSContextRecord).where(*_criteria(actor, kind, unit_id))
    if status:
        query = query.where(QMSContextRecord.status == status)
    rows = list(
        db.scalars(
            query.order_by(QMSContextRecord.code, QMSContextRecord.id).limit(limit).offset(offset)
        )
    )
    result = _read_records(db, rows)
    _verify(db, authenticated, actor, unit_id, "context.read")
    _headers(response, actor)
    return result


@router.get("/qms-scope/current", response_model=RecordRead | None)
def current_scope(
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
) -> RecordRead | None:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", unit_id)
    snapshot = db.scalar(
        select(QMSContextRevision.snapshot)
        .join(QMSContextRecord, QMSContextRecord.id == QMSContextRevision.record_id)
        .where(
            *_criteria(actor, "qms-scope", unit_id),
            QMSContextRevision.tenant_id == actor.tenant_id,
            QMSContextRevision.unit_id == unit_id,
            QMSContextRevision.command == "reviewed",
        )
        .order_by(QMSContextRevision.row_version.desc())
        .limit(1)
    )
    result = RecordRead.model_validate(snapshot) if snapshot is not None else None
    _verify(db, authenticated, actor, unit_id, "context.read")
    _headers(response, actor)
    return result


@router.get("/{kind}/{record_id}", response_model=RecordRead)
def detail(
    kind: Kind,
    record_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
) -> RecordRead:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", unit_id)
    row = _find(db, actor, kind, unit_id, record_id)
    result = _read_records(db, [row])[0]
    _verify(db, authenticated, actor, unit_id, "context.read")
    _headers(response, actor)
    return result


@router.get("/{kind}/{record_id}/history", response_model=list[RecordRevision])
def history(
    kind: Kind,
    record_id: UUID,
    unit_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    before_version: Annotated[int, Query(ge=1, le=2147483647)] = 2147483647,
) -> list[RecordRevision]:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", unit_id)
    _find(db, actor, kind, unit_id, record_id)
    rows = list(
        db.scalars(
            select(QMSContextRevision)
            .where(
                QMSContextRevision.tenant_id == actor.tenant_id,
                QMSContextRevision.unit_id == unit_id,
                QMSContextRevision.record_id == record_id,
                QMSContextRevision.row_version < before_version,
            )
            .order_by(QMSContextRevision.row_version.desc())
            .limit(limit)
        )
    )
    _verify(db, authenticated, actor, unit_id, "context.read")
    _headers(response, actor)
    return [RecordRevision.model_validate(row) for row in rows]


@router.post(
    "/{kind}", response_model=RecordRead, status_code=201, dependencies=[Depends(require_csrf)]
)
def create(
    kind: Kind,
    body: RecordCreate,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> RecordRead:
    actor = actor_context(db, authenticated)
    require_capability(db, "context.read", body.unit_id)
    require_capability(db, "context.manage", body.unit_id)
    _validate_content(kind, body)
    entries, reason = _requirement_values(kind, body)
    now = datetime.now(UTC)
    row = QMSContextRecord(
        **body.model_dump(exclude={"party_requirements", "no_requirements_reason"}),
        party_requirements=entries,
        no_requirements_reason=reason,
        id=uuid4(),
        tenant_id=actor.tenant_id,
        kind=kind,
        status="draft",
        row_version=1,
        decision_note="",
        created_at=now,
        updated_at=now,
        created_by_user_id=actor.user_id,
        content_editor_user_id=actor.user_id,
        updated_by_user_id=actor.user_id,
    )
    try:
        db.add(row)
        result = _persist(db, actor, authenticated, request, row, "created")
    except DBAPIError as error:
        db.rollback()
        _database_error(error)
    _headers(response, actor)
    return result


def _change(
    db: Session,
    auth: Authenticated,
    request: Request,
    response: Response,
    kind: Kind,
    unit_id: UUID,
    record_id: UUID,
    body: RecordEdit | Retire,
    command: Literal["updated", "reviewed", "retired"],
) -> RecordRead:
    actor = actor_context(db, auth)
    require_capability(db, "context.read", unit_id)
    require_capability(db, "context.review" if command == "reviewed" else "context.manage", unit_id)
    if kind == "qms-scope" and command == "retired":
        raise HTTPException(409, "replace the declared QMS scope through independent approval")
    try:
        row = _find(db, actor, kind, unit_id, record_id, lock=True)
        if row.row_version != body.expected_version or row.status == "retired":
            raise HTTPException(409, "record changed or was retired; refresh the register")
        before = _audit_values(row)
        if isinstance(body, RecordEdit):
            _validate_content(kind, body)
            row.party_requirements, row.no_requirements_reason = _requirement_values(
                kind, body, row
            )
            for field, value in body.model_dump(
                exclude={"expected_version", "party_requirements", "no_requirements_reason"}
            ).items():
                setattr(row, field, value)
        else:
            if INVALID_TEXT.search(body.note):
                raise HTTPException(422, "invalid decision note")
            row.decision_note = body.note
            if isinstance(body, Review):
                if actor.user_id in {row.created_by_user_id, row.content_editor_user_id}:
                    raise HTTPException(403, "independent context review required")
                _require_reviewable_party(row)
                if (
                    kind == "qms-scope"
                    and not ScopeDefinition.model_validate(row.scope_definition).ready()
                ):
                    raise HTTPException(409, "complete the QMS scope definition before approval")
                row.review_due_on = body.review_due_on
        row.row_version += 1
        result = _persist(db, actor, auth, request, row, command, before)
    except DBAPIError as error:
        db.rollback()
        _database_error(error)
    _headers(response, actor)
    return result


@router.patch(
    "/{kind}/{record_id}", response_model=RecordRead, dependencies=[Depends(require_csrf)]
)
def edit(
    kind: Kind,
    record_id: UUID,
    unit_id: UUID,
    body: RecordEdit,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> RecordRead:
    return _change(db, authenticated, request, response, kind, unit_id, record_id, body, "updated")


@router.post(
    "/{kind}/{record_id}/review", response_model=RecordRead, dependencies=[Depends(require_csrf)]
)
def review(
    kind: Kind,
    record_id: UUID,
    unit_id: UUID,
    body: Review,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> RecordRead:
    return _change(db, authenticated, request, response, kind, unit_id, record_id, body, "reviewed")


@router.post(
    "/{kind}/{record_id}/retire", response_model=RecordRead, dependencies=[Depends(require_csrf)]
)
def retire(
    kind: Kind,
    record_id: UUID,
    unit_id: UUID,
    body: Retire,
    db: DBSession,
    authenticated: Authenticated,
    request: Request,
    response: Response,
) -> RecordRead:
    return _change(db, authenticated, request, response, kind, unit_id, record_id, body, "retired")
