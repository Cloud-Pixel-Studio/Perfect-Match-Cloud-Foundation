"""Submission and independent review of control implementation evidence."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
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
    QMSControlEvidenceRequirement,
    QMSControlInstance,
    QMSControlInstanceEvidence,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(tags=["control-instance-evidence"])
DBSession = Annotated[Session, Depends(get_db)]
Summary = Annotated[str, StringConstraints(max_length=4000)]
Decision = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class EvidencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    evidence_summary: Summary | None = None
    document_id: UUID | None = None
    document_revision_id: UUID | None = None


class EvidenceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class ReviewCommand(EvidenceCommand):
    target_status: Annotated[str, StringConstraints(pattern="^(accepted|rejected)$")]
    decision: Decision


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    control_instance_id: UUID
    requirement_definition_id: UUID
    sequence: int
    name: str
    description: str
    acceptance_criteria: str
    evidence_type: str
    mandatory: bool
    document_id: UUID | None
    document_revision_id: UUID | None
    evidence_summary: str
    status: str
    submitted_by_user_id: UUID | None
    submitted_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_decision: str
    row_version: int
    created_at: datetime
    updated_at: datetime


def audit_values(row: QMSControlInstanceEvidence) -> dict[str, object]:
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    return {
        "unit_id": str(row.unit_id),
        "process_id": str(row.process_id),
        "control_id": str(row.control_id),
        "control_instance_id": str(row.control_instance_id),
        "requirement_definition_id": str(row.requirement_definition_id),
        "sequence": row.sequence,
        "name": row.name,
        "description_hash": digest(row.description),
        "acceptance_criteria_hash": digest(row.acceptance_criteria),
        "evidence_type": row.evidence_type,
        "mandatory": row.mandatory,
        "document_id": str(row.document_id) if row.document_id else None,
        "document_revision_id": str(row.document_revision_id) if row.document_revision_id else None,
        "evidence_summary_hash": digest(row.evidence_summary),
        "status": row.status,
        "submitted_by_user_id": str(row.submitted_by_user_id) if row.submitted_by_user_id else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "reviewed_by_user_id": str(row.reviewed_by_user_id) if row.reviewed_by_user_id else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "review_decision_hash": digest(row.review_decision),
        "row_version": row.row_version,
    }


def record(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSControlInstanceEvidence,
    action: str,
    before: dict[str, object] | None,
) -> None:
    audit_service.record_control(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        action=action,
        resource_id=row.id,
        request_id=request_id,
        old_values=before,
        new_values=audit_values(row),
    )


def db_error(db: Session, error: DBAPIError) -> None:
    db.rollback()
    original = error.orig
    detail = original.args[0] if original is not None and original.args else None
    state = detail.get("C") if isinstance(detail, dict) else None
    if state in {"23503", "23505", "23514", "40P01", "55P03"}:
        raise HTTPException(409, "evidence, document, review or version conflict") from None
    if state == "42501":
        raise HTTPException(403, "control authority denied") from None
    raise error


def load_for_manage(
    db: Session, actor: OrganizationActor, evidence_id: UUID
) -> QMSControlInstanceEvidence:
    initial = db.scalar(
        select(QMSControlInstanceEvidence).where(
            QMSControlInstanceEvidence.id == evidence_id,
            QMSControlInstanceEvidence.tenant_id == actor.tenant_id,
        )
    )
    if initial is None:
        raise HTTPException(404, "implementation evidence not found")
    parent = db.scalar(
        select(QMSControlInstance)
        .where(
            QMSControlInstance.id == initial.control_instance_id,
            QMSControlInstance.tenant_id == actor.tenant_id,
            QMSControlInstance.status == "active",
        )
        .with_for_update()
    )
    if parent is None:
        raise HTTPException(409, "implementation is not active")
    require_capability(db, "control_instances.manage", parent.unit_id)
    row = db.scalar(
        select(QMSControlInstanceEvidence)
        .where(
            QMSControlInstanceEvidence.id == evidence_id,
            QMSControlInstanceEvidence.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "implementation evidence not found")
    return row


@router.get("/control-instance-evidence", response_model=list[EvidenceResponse])
def list_evidence(
    db: DBSession,
    authenticated: Authenticated,
    instance_id: UUID,
    limit: int = Query(100, ge=1, le=200),
) -> list[QMSControlInstanceEvidence]:
    actor = actor_context(db, authenticated)
    parent = db.scalar(
        select(QMSControlInstance).where(
            QMSControlInstance.id == instance_id,
            QMSControlInstance.tenant_id == actor.tenant_id,
            QMSControlInstance.status == "active",
        )
    )
    if parent is None:
        raise HTTPException(404, "control implementation not found")
    require_capability(db, "control_instances.read", parent.unit_id)
    return list(
        db.scalars(
            select(QMSControlInstanceEvidence)
            .where(
                QMSControlInstanceEvidence.control_instance_id == instance_id,
                QMSControlInstanceEvidence.tenant_id == actor.tenant_id,
            )
            .order_by(QMSControlInstanceEvidence.sequence, QMSControlInstanceEvidence.id)
            .limit(limit)
        )
    )


@router.patch(
    "/control-instance-evidence/{evidence_id}",
    response_model=EvidenceResponse,
    dependencies=[Depends(require_csrf)],
)
def update_evidence(
    request: Request,
    evidence_id: UUID,
    body: EvidencePatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstanceEvidence:
    actor = actor_context(db, authenticated)
    row = load_for_manage(db, actor, evidence_id)
    if row.status not in {"draft", "rejected"}:
        raise HTTPException(409, "evidence can only be edited before review or after rejection")
    if row.row_version != body.expected_version:
        raise HTTPException(409, "evidence changed; refresh before editing")
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes:
        raise HTTPException(422, "provide evidence changes")
    if changes.get("evidence_summary", "") is None:
        raise HTTPException(422, "evidence summary cannot be null")
    if "document_id" in changes or "document_revision_id" in changes:
        if row.document_id is not None or row.document_revision_id is not None:
            require_capability(db, "documents.read", row.unit_id)
        if (changes.get("document_id", row.document_id) is None) != (
            changes.get("document_revision_id", row.document_revision_id) is None
        ):
            raise HTTPException(422, "select both a controlled document and its revision")
        if changes.get("document_id", row.document_id) is not None:
            require_capability(db, "documents.read", row.unit_id)
    before = audit_values(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.flush()
        record(
            db, actor, request.state.request_id, row, "control_instance_evidence.updated", before
        )
        db.commit()
    except DBAPIError as error:
        db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/control-instance-evidence/{evidence_id}/submit",
    response_model=EvidenceResponse,
    dependencies=[Depends(require_csrf)],
)
def submit_evidence(
    request: Request,
    evidence_id: UUID,
    body: EvidenceCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstanceEvidence:
    actor = actor_context(db, authenticated)
    row = load_for_manage(db, actor, evidence_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "evidence changed; refresh before editing")
    if row.status not in {"draft", "rejected"}:
        raise HTTPException(409, "evidence is not ready to submit")
    if not row.evidence_summary.strip() and row.document_revision_id is None:
        raise HTTPException(422, "add an evidence summary or link a released controlled revision")
    before = audit_values(row)
    row.status = "submitted"
    row.submitted_by_user_id = actor.user_id
    row.submitted_at = datetime.now(UTC)
    row.reviewed_by_user_id = None
    row.reviewed_at = None
    row.review_decision = ""
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    try:
        db.connection().exec_driver_sql(
            "SELECT set_config('app.control_evidence_workflow','on',true)"
        )
        db.flush()
        record(
            db, actor, request.state.request_id, row, "control_instance_evidence.submitted", before
        )
        db.commit()
    except DBAPIError as error:
        db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


@router.post(
    "/control-instance-evidence/{evidence_id}/review",
    response_model=EvidenceResponse,
    dependencies=[Depends(require_csrf)],
)
def review_evidence(
    request: Request,
    evidence_id: UUID,
    body: ReviewCommand,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlInstanceEvidence:
    actor = actor_context(db, authenticated)
    row = load_for_manage(db, actor, evidence_id)
    if row.status != "submitted":
        raise HTTPException(409, "only submitted evidence can be reviewed")
    if row.row_version != body.expected_version:
        raise HTTPException(409, "evidence changed; refresh before editing")
    if row.submitted_by_user_id == actor.user_id:
        raise HTTPException(403, "the submitter cannot review their own evidence")
    before = audit_values(row)
    row.status = body.target_status
    row.reviewed_by_user_id = actor.user_id
    row.reviewed_at = datetime.now(UTC)
    row.review_decision = body.decision
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    action = (
        "control_instance_evidence.accepted"
        if body.target_status == "accepted"
        else "control_instance_evidence.rejected"
    )
    try:
        db.connection().exec_driver_sql(
            "SELECT set_config('app.control_evidence_workflow','on',true)"
        )
        db.flush()
        record(db, actor, request.state.request_id, row, action, before)
        db.commit()
    except DBAPIError as error:
        db_error(db, error)
    except Exception:
        db.rollback()
        raise
    return row


def generate_for_instance(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    instance: QMSControlInstance,
    now: datetime,
) -> None:
    requirements = db.scalars(
        select(QMSControlEvidenceRequirement)
        .where(
            QMSControlEvidenceRequirement.tenant_id == actor.tenant_id,
            QMSControlEvidenceRequirement.unit_id == instance.unit_id,
            QMSControlEvidenceRequirement.process_id == instance.process_id,
            QMSControlEvidenceRequirement.control_id == instance.control_id,
            QMSControlEvidenceRequirement.active.is_(True),
        )
        .order_by(QMSControlEvidenceRequirement.sequence, QMSControlEvidenceRequirement.id)
    ).all()
    for requirement in requirements:
        row = QMSControlInstanceEvidence(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            unit_id=instance.unit_id,
            process_id=instance.process_id,
            control_id=instance.control_id,
            control_instance_id=instance.id,
            requirement_definition_id=requirement.id,
            sequence=requirement.sequence,
            name=requirement.name,
            description=requirement.description,
            acceptance_criteria=requirement.acceptance_criteria,
            evidence_type=requirement.evidence_type,
            mandatory=requirement.mandatory,
            document_id=None,
            document_revision_id=None,
            evidence_summary="",
            status="draft",
            submitted_by_user_id=None,
            submitted_at=None,
            reviewed_by_user_id=None,
            reviewed_at=None,
            review_decision="",
            row_version=1,
            created_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        record(db, actor, request_id, row, "control_instance_evidence.created", None)
