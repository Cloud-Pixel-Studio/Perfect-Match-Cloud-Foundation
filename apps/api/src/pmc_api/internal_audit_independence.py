"""Append-only independence assessment and conservative preparation diagnostics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
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
from pmc_api.internal_audits import _audit, _audit_values, _db_error
from pmc_api.models import QMSAuditIndependenceReview, QMSInternalAudit
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(prefix="/internal-audits/audits", tags=["audit-independence"])
DB = Annotated[Session, Depends(get_db)]


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_audit_version: int = Field(ge=1)
    expected_review_version: int = Field(ge=0)
    decision: Literal["confirmed", "override", "withdrawn"]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    independence_attested: StrictBool

    @model_validator(mode="after")
    def attestation(self) -> ReviewInput:
        if self.independence_attested != (self.decision != "withdrawn"):
            raise ValueError("affirm the independence assessment, or withdraw without affirmation")
        return self


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    audit_id: UUID
    review_version: int
    source_audit_version: int
    decision: str
    notes: str
    independence_attested: bool
    reviewer_user_id: UUID
    reviewer_name_snapshot: str
    lead_auditor_user_id: UUID | None
    created_at: datetime


class PreparationCheck(BaseModel):
    code: str
    label: str
    status: Literal["passed", "blocked", "unverified"]
    detail: str


class ExecutionAuthority(BaseModel):
    status: Literal["passed", "blocked", "unverified"]
    planned_auditors: int | None = None
    authorized_auditors: int | None = None


class IndependenceSummary(BaseModel):
    audit_id: UUID
    unit_id: UUID
    audit_version: int
    actor_user_id: UUID
    review_version: int
    latest_review: ReviewRead | None
    review_current: bool
    can_review: bool
    can_withdraw: bool
    review_blockers: list[str]
    execution_authority: ExecutionAuthority
    ready_for_execution: Literal[False] = False
    checks: list[PreparationCheck]


class ReviewResult(BaseModel):
    review: ReviewRead
    audit_version: int


def _latest(db: Session, parent: QMSInternalAudit) -> QMSAuditIndependenceReview | None:
    return db.scalar(
        select(QMSAuditIndependenceReview)
        .where(
            QMSAuditIndependenceReview.audit_id == parent.id,
            QMSAuditIndependenceReview.tenant_id == parent.tenant_id,
            QMSAuditIndependenceReview.unit_id == parent.unit_id,
        )
        .order_by(QMSAuditIndependenceReview.review_version.desc())
        .limit(1)
    )


def _facts(db: Session, parent: QMSInternalAudit, actor_id: UUID) -> dict[str, bool | int]:
    row = (
        db.execute(
            text("""
SELECT
 (SELECT count(*) FROM qms_audit_scopes WHERE audit_id=:id AND status='active') AS scopes,
 (SELECT count(*) FROM qms_audit_criteria WHERE audit_id=:id AND status='active') AS criteria,
 (SELECT count(*) FROM qms_audit_agenda_items WHERE audit_id=:id AND status='active') AS agenda,
 EXISTS(SELECT 1 FROM qms_audit_team_members t JOIN organization_member_directory() d
   ON d.user_id=t.user_id
   WHERE t.audit_id=:id AND t.user_id=:lead AND t.status='active'
   AND t.team_role='auditor') AS lead_active,
 EXISTS(SELECT 1 FROM qms_audit_team_members WHERE audit_id=:id AND user_id=:actor
   AND status='active') AS actor_in_team,
 EXISTS(SELECT 1 FROM qms_audit_team_members t WHERE t.audit_id=:id AND t.status='active'
   AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=t.user_id))
   AS inactive_people,
 qms_has_capability('audits.review',:unit) AS review_authority,
 (CAST(:program AS uuid) IS NULL OR EXISTS(SELECT 1 FROM qms_audit_programs WHERE id=:program
   AND state IN ('approved','active'))) AS program_active
"""),
            {
                "id": parent.id,
                "lead": parent.lead_auditor_user_id,
                "actor": actor_id,
                "unit": parent.unit_id,
                "program": parent.program_id,
            },
        )
        .mappings()
        .one()
    )
    return {key: row[key] for key in row}


def _eligibility(
    parent: QMSInternalAudit, actor_id: UUID, facts: dict[str, bool | int]
) -> list[str]:
    blockers = []
    if not facts["review_authority"]:
        blockers.append("An explicit audits.review responsibility is required.")
    if parent.state != "planned":
        blockers.append("Schedule this audit before recording an independence decision.")
    if (
        actor_id in {parent.created_by_user_id, parent.lead_auditor_user_id}
        or facts["actor_in_team"]
    ):
        blockers.append("The reviewer must be outside audit creation and the active audit team.")
    return blockers


def _plan_blockers(facts: dict[str, bool | int]) -> list[str]:
    blockers = []
    if not facts["lead_active"]:
        blockers.append("Assign the lead as an active planned auditor in this company.")
    if not all(facts[key] for key in ["scopes", "criteria", "agenda"]):
        blockers.append("Complete active structured scope, criteria and agenda before review.")
    if facts["inactive_people"]:
        blockers.append("Reconcile planned people whose company membership is no longer active.")
    return blockers


def _execution_authority(
    db: Session, parent: QMSInternalAudit, can_review: bool
) -> ExecutionAuthority:
    if not can_review:
        return ExecutionAuthority(status="unverified")
    try:
        row = db.execute(
            text(
                "SELECT planned_auditors,authorized_auditors "
                "FROM qms_audit_execution_authority(:audit)"
            ),
            {"audit": parent.id},
        ).one()
    except DBAPIError as error:
        _db_error(db, error)
    return ExecutionAuthority(
        status="passed"
        if row.planned_auditors > 0 and row.planned_auditors == row.authorized_auditors
        else "blocked",
        planned_auditors=row.planned_auditors,
        authorized_auditors=row.authorized_auditors,
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get(
    "/{audit_id}/independence",
    response_model=IndependenceSummary,
    dependencies=[Depends(_no_store)],
)
def get_independence(audit_id: UUID, db: DB, authenticated: Authenticated) -> IndependenceSummary:
    actor = actor_context(db, authenticated)
    parent = _audit(db, actor, audit_id)
    version = parent.row_version
    review = _latest(db, parent)
    facts = _facts(db, parent, actor.user_id)
    authority = _execution_authority(db, parent, bool(facts["review_authority"]))
    base_blockers = _eligibility(parent, actor.user_id, facts)
    current = bool(
        review
        and review.source_audit_version == version
        and review.decision != "withdrawn"
        and parent.state == "planned"
    )
    if current and review:
        current = bool(
            db.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM organization_member_directory() "
                    "WHERE user_id=:person)"
                ),
                {"person": review.reviewer_user_id},
            )
        )
    checks = [
        PreparationCheck(
            code="scheduled",
            label="Scheduled audit",
            status="passed" if parent.state == "planned" else "blocked",
            detail="A scheduled record remains a planning record.",
        ),
        PreparationCheck(
            code="scope",
            label="Structured scope",
            status="passed" if facts["scopes"] else "blocked",
            detail=f"{facts['scopes']} active scope items.",
        ),
        PreparationCheck(
            code="criteria",
            label="Audit criteria",
            status="passed" if facts["criteria"] else "blocked",
            detail=f"{facts['criteria']} active criteria.",
        ),
        PreparationCheck(
            code="agenda",
            label="Audit agenda",
            status="passed" if facts["agenda"] else "blocked",
            detail=f"{facts['agenda']} active activities; no cross-audit calendar verification.",
        ),
        PreparationCheck(
            code="lead",
            label="Lead and planned participants",
            status="passed" if facts["lead_active"] and not facts["inactive_people"] else "blocked",
            detail=(
                "The lead must be an active planned auditor; all planned people must be "
                "active company members."
            ),
        ),
        PreparationCheck(
            code="program",
            label="Linked audit program",
            status="passed" if facts["program_active"] else "blocked",
            detail="A linked program must be approved or active; standalone planning is allowed.",
        ),
        PreparationCheck(
            code="independence",
            label="Independence assessment",
            status="passed" if current else "blocked",
            detail=(
                "Recorded reviewer assessment applies only to its exact planning version. An "
                "override remains an explicit exception."
            ),
        ),
        PreparationCheck(
            code="execution_authority",
            label="Execution authority",
            status=authority.status,
            detail=(
                f"{authority.authorized_auditors} of {authority.planned_auditors} planned auditors "
                "currently have explicit read and execution responsibilities in this unit. "
                "Assignment grants no access; later changes require revalidation."
                if authority.status != "unverified"
                else "A reviewer can verify the planned team's current execution access. "
                "This view does not expose another person's detailed permissions."
            ),
        ),
        PreparationCheck(
            code="competence",
            label="Auditor competence",
            status="unverified",
            detail=(
                "Qualification and competence records are not implemented; a reviewer "
                "attestation does not replace them."
            ),
        ),
        PreparationCheck(
            code="execution_workflow",
            label="Execution workflow",
            status="blocked",
            detail=(
                "The ready/start commands and evidence workflow are not implemented. This "
                "diagnostic cannot authorize execution."
            ),
        ),
    ]
    db.refresh(parent)
    if parent.row_version != version:
        raise HTTPException(409, "plan changed during preparation check; refresh")
    return IndependenceSummary(
        audit_id=parent.id,
        unit_id=parent.unit_id,
        audit_version=version,
        actor_user_id=actor.user_id,
        review_version=review.review_version if review else 0,
        latest_review=ReviewRead.model_validate(review) if review else None,
        review_current=current,
        can_review=not base_blockers and not _plan_blockers(facts),
        can_withdraw=not base_blockers and bool(review and review.decision != "withdrawn"),
        review_blockers=base_blockers + _plan_blockers(facts),
        checks=checks,
        execution_authority=authority,
    )


@router.get("/{audit_id}/independence/reviews", response_model=list[ReviewRead])
def list_reviews(
    audit_id: UUID,
    db: DB,
    authenticated: Authenticated,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[QMSAuditIndependenceReview]:
    actor = actor_context(db, authenticated)
    parent = _audit(db, actor, audit_id)
    return list(
        db.scalars(
            select(QMSAuditIndependenceReview)
            .where(
                QMSAuditIndependenceReview.audit_id == parent.id,
                QMSAuditIndependenceReview.tenant_id == parent.tenant_id,
                QMSAuditIndependenceReview.unit_id == parent.unit_id,
            )
            .order_by(QMSAuditIndependenceReview.review_version.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def _review_values(
    parent: QMSInternalAudit, review: QMSAuditIndependenceReview | None
) -> dict[str, object]:
    values = _audit_values(parent)
    for field in [
        "independence_status",
        "independence_reviewed_by_user_id",
        "independence_reviewed_at",
        "independence_notes_hash",
    ]:
        values.pop(field, None)
    values["independence_review_version"] = review.review_version if review else 0
    if review:
        values.update(
            independence_review_id=str(review.id),
            independence_source_audit_version=review.source_audit_version,
            independence_decision=review.decision,
            independence_reviewer_id=str(review.reviewer_user_id),
            independence_notes_hash=hashlib.sha256(review.notes.encode()).hexdigest(),
        )
    return values


@router.post(
    "/{audit_id}/independence/reviews",
    response_model=ReviewResult,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_review(
    audit_id: UUID, body: ReviewInput, request: Request, db: DB, authenticated: Authenticated
) -> ReviewResult:
    actor = actor_context(db, authenticated)
    parent = _audit(db, actor, audit_id)
    require_capability(db, "audits.review", parent.unit_id)
    parent = _audit(db, actor, audit_id, lock=True)
    previous = _latest(db, parent)
    if (
        parent.row_version != body.expected_audit_version
        or (previous.review_version if previous else 0) != body.expected_review_version
    ):
        raise HTTPException(409, "plan or independence history changed; refresh")
    facts = _facts(db, parent, actor.user_id)
    blockers = _eligibility(parent, actor.user_id, facts)
    if body.decision != "withdrawn":
        blockers += _plan_blockers(facts)
    elif previous is None or previous.decision == "withdrawn":
        blockers.append("No recorded decision remains to withdraw.")
    if blockers:
        raise HTTPException(409, blockers[0])
    now = datetime.now(UTC)
    if previous:
        now = max(now, previous.created_at + timedelta(microseconds=1))
    review = QMSAuditIndependenceReview(
        id=uuid4(),
        tenant_id=parent.tenant_id,
        unit_id=parent.unit_id,
        audit_id=parent.id,
        review_version=body.expected_review_version + 1,
        source_audit_version=parent.row_version,
        decision=body.decision,
        notes=body.notes,
        independence_attested=body.independence_attested,
        reviewer_user_id=actor.user_id,
        reviewer_name_snapshot=actor.display_name,
        lead_auditor_user_id=parent.lead_auditor_user_id,
        created_at=now,
    )
    before = _review_values(parent, previous)
    try:
        db.add(review)
        db.flush()
        values = _review_values(parent, review)
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
            new_values=values,
        )
        result = ReviewResult(
            review=ReviewRead.model_validate(review), audit_version=parent.row_version
        )
        db.commit()
    except DBAPIError as error:
        _db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return result
