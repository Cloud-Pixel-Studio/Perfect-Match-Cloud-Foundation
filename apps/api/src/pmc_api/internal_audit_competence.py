"""Audit-specific human competence assessments supported by controlled documents."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.internal_audits import _audit, _db_error
from pmc_api.models import QMSAuditCompetenceReview, QMSAuditTeamMember, QMSInternalAudit
from pmc_api.qms_access import actor_context, require_capability

DB = Annotated[Session, Depends(get_db)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(
    prefix="/internal-audits/audits", tags=["audit-competence"], dependencies=[Depends(_no_store)]
)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_review_version: int = Field(ge=0)
    team_member_id: UUID
    decision: Literal["confirmed", "withdrawn"]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    competence_attested: StrictBool
    document_id: UUID | None = None
    document_revision_id: UUID | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def source_and_attestation(self) -> ReviewInput:
        confirmation = self.decision == "confirmed"
        if self.competence_attested != confirmation:
            raise ValueError("affirm competence for confirmation, not withdrawal")
        source = [self.document_id, self.document_revision_id, self.valid_until]
        if (confirmation and any(value is None for value in source)) or (
            not confirmation and any(value is not None for value in source)
        ):
            raise ValueError("confirmation requires source and validity; withdrawal preserves them")
        return self


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audit_id: UUID
    unit_id: UUID
    team_member_id: UUID
    subject_user_id: UUID
    subject_name_snapshot: str
    review_version: int
    source_audit_version: int
    decision: Literal["confirmed", "withdrawn"]
    notes: str
    competence_attested: bool
    document_id: UUID
    document_revision_id: UUID
    document_code_snapshot: str
    document_title_snapshot: str
    document_revision_snapshot: str
    file_sha256: str
    valid_until: date
    reviewer_user_id: UUID
    reviewer_name_snapshot: str
    created_at: datetime


class AuditorRead(BaseModel):
    team_member_id: UUID
    user_id: UUID
    display_name_snapshot: str
    member_active: bool
    assignment_active: bool
    assessment_status: Literal[
        "missing",
        "current",
        "withdrawn",
        "outdated",
        "expired",
        "evidence_unavailable",
        "member_inactive",
        "reviewer_inactive",
        "assignment_inactive",
    ]
    latest_review: ReviewRead | None
    review_current: bool


class CompetenceSummary(BaseModel):
    audit_id: UUID
    unit_id: UUID
    audit_version: int
    actor_user_id: UUID
    review_version: int
    can_review: bool
    review_blockers: list[str]
    planned_auditors: int
    current_assessments: int
    auditors: list[AuditorRead]


class ReviewResult(BaseModel):
    review: ReviewRead
    audit_version: int


class DocumentOption(BaseModel):
    document_id: UUID
    document_revision_id: UUID
    code: str
    title: str
    revision: str
    file_sha256: str


# Invoker-only reads. Each source retains its normal RLS/capabilities; no definer or grant mirror.
_ROSTER = """
WITH latest AS (
 SELECT DISTINCT ON(team_member_id) * FROM qms_audit_competence_reviews
 WHERE audit_id=:audit AND tenant_id=:tenant AND unit_id=:unit
 ORDER BY team_member_id,review_version DESC
), roster AS (
 SELECT t.id AS team_member_id,t.user_id,t.display_name_snapshot,t.created_at,
 (t.status='active' AND t.team_role='auditor') AS assignment_active,
 EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=t.user_id) AS member_active,
 r.id AS latest_review_id,
 CASE
  WHEN t.status<>'active' OR t.team_role<>'auditor' THEN 'assignment_inactive'
  WHEN NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=t.user_id)
   THEN 'member_inactive'
  WHEN r.id IS NULL THEN 'missing'
  WHEN r.decision='withdrawn' THEN 'withdrawn'
  WHEN r.source_audit_version<>:version OR :state<>'planned' THEN 'outdated'
  WHEN r.valid_until<:today OR r.valid_until<:ends THEN 'expired'
  WHEN NOT EXISTS(SELECT 1 FROM qms_documents d JOIN qms_document_revisions v
   ON v.document_id=d.id AND v.tenant_id=d.tenant_id
   WHERE d.id=r.document_id AND d.tenant_id=:tenant AND d.unit_id=:unit AND d.status='active'
    AND v.id=r.document_revision_id AND v.status='active' AND v.file_state='clean'
    AND v.file_sha256=r.file_sha256) THEN 'evidence_unavailable'
  WHEN NOT EXISTS(SELECT 1 FROM organization_member_directory() d
   WHERE d.user_id=r.reviewer_user_id)
   THEN 'reviewer_inactive'
  ELSE 'current'
 END AS assessment_status
 FROM qms_audit_team_members t LEFT JOIN latest r ON r.team_member_id=t.id
 WHERE t.audit_id=:audit AND t.tenant_id=:tenant AND t.unit_id=:unit
  AND ((t.status='active' AND t.team_role='auditor') OR r.id IS NOT NULL)
)
"""


def _params(parent: QMSInternalAudit) -> dict[str, object]:
    return {
        "audit": parent.id,
        "tenant": parent.tenant_id,
        "unit": parent.unit_id,
        "version": parent.row_version,
        "state": parent.state,
        "today": datetime.now(UTC).date(),
        "ends": parent.planned_end,
    }


def _counts(db: Session, parent: QMSInternalAudit) -> tuple[int, int]:
    row = db.execute(
        text(
            _ROSTER  # noqa: S608 -- fixed CTE/literals; all request values are bound.
            + "SELECT count(*) FILTER(WHERE assignment_active), "
            "count(*) FILTER(WHERE assignment_active AND assessment_status='current') FROM roster"
        ),
        _params(parent),
    ).one()
    return int(row[0]), int(row[1])


def _latest(
    db: Session, parent: QMSInternalAudit, member: UUID | None = None
) -> QMSAuditCompetenceReview | None:
    query = select(QMSAuditCompetenceReview).where(
        QMSAuditCompetenceReview.audit_id == parent.id,
        QMSAuditCompetenceReview.tenant_id == parent.tenant_id,
        QMSAuditCompetenceReview.unit_id == parent.unit_id,
    )
    if member is not None:
        query = query.where(QMSAuditCompetenceReview.team_member_id == member)
    return db.scalar(query.order_by(QMSAuditCompetenceReview.review_version.desc()).limit(1))


def _blockers(db: Session, parent: QMSInternalAudit, actor_id: UUID) -> list[str]:
    blockers = []
    if not db.scalar(
        text("SELECT qms_has_capability('audits.review',:unit)"), {"unit": parent.unit_id}
    ):
        blockers.append("An explicit audits.review responsibility is required.")
    if parent.state != "planned":
        blockers.append("Schedule this audit before recording competence assessments.")
    if actor_id in {parent.created_by_user_id, parent.lead_auditor_user_id} or db.scalar(
        select(QMSAuditTeamMember.id)
        .where(
            QMSAuditTeamMember.audit_id == parent.id,
            QMSAuditTeamMember.user_id == actor_id,
            QMSAuditTeamMember.status == "active",
        )
        .limit(1)
    ):
        blockers.append("The reviewer must be outside audit creation and the active team.")
    return blockers


def _parent(db: Session, authenticated: Authenticated, audit_id: UUID) -> QMSInternalAudit:
    actor = actor_context(db, authenticated)
    parent = _audit(db, actor, audit_id)
    require_capability(db, "documents.read", parent.unit_id)
    return parent


@router.get("/{audit_id}/competence", response_model=CompetenceSummary)
def get_competence(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> CompetenceSummary:
    parent = _parent(db, authenticated, audit_id)
    actor = actor_context(db, authenticated)
    version = parent.row_version
    latest = _latest(db, parent)
    blockers = _blockers(db, parent, actor.user_id)
    snapshot = (
        db.execute(
            text(
                _ROSTER  # noqa: S608 -- fixed SQL literals, all request values bound.
                + """, totals AS (
 SELECT count(*) FILTER(WHERE assignment_active) AS planned_auditors,
 count(*) FILTER(WHERE assignment_active AND assessment_status='current') AS current_assessments
 FROM roster
), page AS (
 SELECT * FROM roster ORDER BY created_at,team_member_id LIMIT :limit OFFSET :offset
)
SELECT totals.planned_auditors,totals.current_assessments,page.*
 FROM totals LEFT JOIN page ON true ORDER BY page.created_at,page.team_member_id
"""
            ),
            {**_params(parent), "limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    planned = int(snapshot[0]["planned_auditors"])
    current = int(snapshot[0]["current_assessments"])
    rows = [row for row in snapshot if row["team_member_id"] is not None]
    ids = [row["latest_review_id"] for row in rows if row["latest_review_id"]]
    reviews = {
        review.id: review
        for review in db.scalars(
            select(QMSAuditCompetenceReview).where(QMSAuditCompetenceReview.id.in_(ids))
        )
    }
    auditors = [
        AuditorRead(
            team_member_id=row["team_member_id"],
            user_id=row["user_id"],
            display_name_snapshot=row["display_name_snapshot"],
            assignment_active=row["assignment_active"],
            member_active=row["member_active"],
            assessment_status=row["assessment_status"],
            latest_review=ReviewRead.model_validate(reviews[row["latest_review_id"]])
            if row["latest_review_id"] in reviews
            else None,
            review_current=row["assessment_status"] == "current",
        )
        for row in rows
    ]
    db.expire(parent)
    parent = _audit(db, actor, audit_id)
    require_capability(db, "documents.read", parent.unit_id)
    last = _latest(db, parent)
    if parent.row_version != version or (last.review_version if last else 0) != (
        latest.review_version if latest else 0
    ):
        raise HTTPException(409, "plan or competence history changed during check; refresh")
    return CompetenceSummary(
        audit_id=parent.id,
        unit_id=parent.unit_id,
        audit_version=version,
        actor_user_id=actor.user_id,
        review_version=latest.review_version if latest else 0,
        can_review=not blockers,
        review_blockers=blockers,
        planned_auditors=planned,
        current_assessments=current,
        auditors=auditors,
    )


@router.get("/{audit_id}/competence/reviews", response_model=list[ReviewRead])
def list_reviews(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditCompetenceReview]:
    parent = _parent(db, authenticated, audit_id)
    return list(
        db.scalars(
            select(QMSAuditCompetenceReview)
            .where(
                QMSAuditCompetenceReview.audit_id == parent.id,
                QMSAuditCompetenceReview.tenant_id == parent.tenant_id,
                QMSAuditCompetenceReview.unit_id == parent.unit_id,
            )
            .order_by(QMSAuditCompetenceReview.review_version.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/{audit_id}/competence/documents", response_model=list[DocumentOption])
def list_documents(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    q: Annotated[str, Query(max_length=160)] = "",
) -> list[DocumentOption]:
    parent = _parent(db, authenticated, audit_id)
    # Parameter-bound ILIKE; user wildcards are treated literally.
    pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = db.execute(
        text("""SELECT d.id AS document_id,r.id AS document_revision_id,
 d.code,d.title,r.revision,r.file_sha256
 FROM qms_documents d JOIN qms_document_revisions r
 ON r.document_id=d.id AND r.tenant_id=d.tenant_id
 WHERE d.tenant_id=:tenant AND d.unit_id=:unit AND d.status='active'
 AND r.status='active' AND r.file_state='clean'
 AND (d.code ILIKE :pattern OR d.title ILIKE :pattern)
 ORDER BY d.code,d.id,r.id LIMIT :limit OFFSET :offset"""),
        {
            "tenant": parent.tenant_id,
            "unit": parent.unit_id,
            "pattern": pattern,
            "limit": limit,
            "offset": offset,
        },
    ).mappings()
    return [DocumentOption.model_validate(row) for row in rows]


def _values(parent: QMSInternalAudit, review: QMSAuditCompetenceReview | None) -> dict[str, object]:
    values: dict[str, object] = {
        "unit_id": str(parent.unit_id),
        "row_version": parent.row_version,
        "competence_review_version": review.review_version if review else 0,
    }
    if review:
        values.update(
            competence_review_id=str(review.id),
            competence_source_audit_version=review.source_audit_version,
            competence_team_member_id=str(review.team_member_id),
            competence_subject_user_id=str(review.subject_user_id),
            competence_decision=review.decision,
            competence_reviewer_id=str(review.reviewer_user_id),
            competence_document_id=str(review.document_id),
            competence_document_revision_id=str(review.document_revision_id),
            competence_file_sha256=review.file_sha256,
            competence_valid_until=review.valid_until.isoformat(),
            competence_notes_hash=hashlib.sha256(review.notes.encode()).hexdigest(),
        )
    return values


@router.post(
    "/{audit_id}/competence/reviews",
    response_model=ReviewResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_review(
    audit_id: UUID, body: ReviewInput, request: Request, db: DB, authenticated: Authenticated
) -> ReviewResult:
    parent = _parent(db, authenticated, audit_id)
    actor = actor_context(db, authenticated)
    require_capability(db, "audits.review", parent.unit_id)
    parent = _audit(db, actor, audit_id, lock=True)
    previous = _latest(db, parent)
    if (
        parent.row_version != body.expected_audit_version
        or (previous.review_version if previous else 0) != body.expected_review_version
    ):
        raise HTTPException(409, "plan or competence history changed; refresh")
    blockers = _blockers(db, parent, actor.user_id)
    if blockers:
        raise HTTPException(409, blockers[0])
    member = db.scalar(
        select(QMSAuditTeamMember).where(
            QMSAuditTeamMember.id == body.team_member_id,
            QMSAuditTeamMember.audit_id == parent.id,
            QMSAuditTeamMember.tenant_id == parent.tenant_id,
            QMSAuditTeamMember.unit_id == parent.unit_id,
        )
    )
    if member is None:
        raise HTTPException(404, "audit assignment unavailable")
    prior_target = _latest(db, parent, member.id)
    if body.decision == "withdrawn" and (
        prior_target is None or prior_target.decision != "confirmed"
    ):
        raise HTTPException(409, "no competence assessment to withdraw")
    row = QMSAuditCompetenceReview(
        id=uuid4(),
        tenant_id=parent.tenant_id,
        unit_id=parent.unit_id,
        audit_id=parent.id,
        team_member_id=member.id,
        subject_user_id=member.user_id,
        subject_name_snapshot=member.display_name_snapshot,
        review_version=body.expected_review_version + 1,
        source_audit_version=parent.row_version,
        decision=body.decision,
        notes=body.notes,
        competence_attested=body.competence_attested,
        document_id=body.document_id,
        document_revision_id=body.document_revision_id,
        valid_until=body.valid_until,
        document_code_snapshot="",
        document_title_snapshot="",
        document_revision_snapshot="",
        file_sha256="",
        reviewer_user_id=actor.user_id,
        reviewer_name_snapshot=actor.display_name,
        created_at=datetime.now(UTC),
    )
    before = _values(parent, previous)
    try:
        db.add(row)
        db.flush()
        db.refresh(row)
        audit_service.record_internal_audit(
            db,
            tenant_id=actor.tenant_id,
            actor_user_id=actor.user_id,
            actor_display_name=actor.display_name,
            actor_role=actor.role,
            action="internal_audit.updated",
            resource_id=parent.id,
            request_id=request.state.request_id,
            old_values=before,
            new_values=_values(parent, row),
        )
        result = ReviewResult(
            review=ReviewRead.model_validate(row), audit_version=parent.row_version
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return result
