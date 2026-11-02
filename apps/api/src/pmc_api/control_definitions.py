"""Reusable activities and evidence requirements for controlled QMS methods."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.auth import Authenticated, require_csrf
from pmc_api.database import get_db
from pmc_api.models import QMSControl, QMSControlActivity, QMSControlEvidenceRequirement
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import actor_context, require_capability

router = APIRouter(tags=["control-definitions"])
DBSession = Annotated[Session, Depends(get_db)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
LongText = Annotated[str, StringConstraints(max_length=4000)]
DefinitionKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
ACTIVITY_KINDS = (
    "qms_implementation project_administration readiness_assessment "
    "certification_preparation transition gap_remediation other"
)
EVIDENCE_TYPES = "document record report approval system_record meeting training metric other"


class ActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(default=10, ge=0, le=1_000_000)
    name: Name
    description: LongText = ""
    objective: LongText = ""
    why_it_matters: LongText = ""
    implementation_steps: LongText = ""
    success_criteria: LongText = ""
    activity_kind: Annotated[
        str, StringConstraints(pattern=f"^({'|'.join(ACTIVITY_KINDS.split())})$")
    ] = "qms_implementation"
    readiness_required: bool = True
    responsible_role: Annotated[str, StringConstraints(max_length=160)] = ""
    expected_output: LongText = ""
    evidence_expectations: LongText = ""
    definition_key: DefinitionKey | None = None

    @model_validator(mode="after")
    def exclude_administration_from_readiness(self) -> ActivityInput:
        if self.activity_kind == "project_administration":
            self.readiness_required = False
        return self


class ActivityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int | None = Field(default=None, ge=0, le=1_000_000)
    name: Name | None = None
    description: LongText | None = None
    objective: LongText | None = None
    why_it_matters: LongText | None = None
    implementation_steps: LongText | None = None
    success_criteria: LongText | None = None
    activity_kind: (
        Annotated[str, StringConstraints(pattern=f"^({'|'.join(ACTIVITY_KINDS.split())})$")] | None
    ) = None
    readiness_required: bool | None = None
    responsible_role: Annotated[str, StringConstraints(max_length=160)] | None = None
    expected_output: LongText | None = None
    evidence_expectations: LongText | None = None
    definition_key: DefinitionKey | None = None
    active: bool | None = None
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def exclude_administration_from_readiness(self) -> ActivityPatch:
        if self.activity_kind == "project_administration":
            self.readiness_required = False
        return self


class EvidenceRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(default=10, ge=0, le=1_000_000)
    name: Name
    description: LongText = ""
    acceptance_criteria: LongText = ""
    evidence_type: Annotated[
        str, StringConstraints(pattern=f"^({'|'.join(EVIDENCE_TYPES.split())})$")
    ] = "record"
    mandatory: bool = True
    definition_key: DefinitionKey | None = None


class EvidenceRequirementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int | None = Field(default=None, ge=0, le=1_000_000)
    name: Name | None = None
    description: LongText | None = None
    acceptance_criteria: LongText | None = None
    evidence_type: (
        Annotated[str, StringConstraints(pattern=f"^({'|'.join(EVIDENCE_TYPES.split())})$")] | None
    ) = None
    mandatory: bool | None = None
    definition_key: DefinitionKey | None = None
    active: bool | None = None
    expected_version: int = Field(ge=1)


class ActivityResponse(ActivityInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    process_id: UUID
    control_id: UUID
    active: bool
    row_version: int
    created_at: datetime
    updated_at: datetime


class EvidenceRequirementResponse(EvidenceRequirementInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    unit_id: UUID
    process_id: UUID
    control_id: UUID
    active: bool
    row_version: int
    created_at: datetime
    updated_at: datetime


def _control(db: Session, actor: OrganizationActor, control_id: UUID, manage: bool) -> QMSControl:
    query = select(QMSControl).where(
        QMSControl.id == control_id, QMSControl.tenant_id == actor.tenant_id
    )
    if manage:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "control not found")
    require_capability(db, "controls.manage" if manage else "controls.read", row.unit_id)
    if manage and row.state != "draft":
        raise HTTPException(409, "method definitions are locked after control activation")
    return row


def _audit_values(row: QMSControlActivity | QMSControlEvidenceRequirement) -> dict[str, object]:
    values: dict[str, object] = {
        "unit_id": str(row.unit_id),
        "process_id": str(row.process_id),
        "control_id": str(row.control_id),
        "sequence": row.sequence,
        "name": row.name,
        "description_hash": hashlib.sha256(row.description.encode()).hexdigest(),
        "definition_key": row.definition_key,
        "active": row.active,
        "row_version": row.row_version,
    }
    if isinstance(row, QMSControlActivity):
        values.update(
            {
                "objective_hash": hashlib.sha256(row.objective.encode()).hexdigest(),
                "why_it_matters_hash": hashlib.sha256(row.why_it_matters.encode()).hexdigest(),
                "implementation_steps_hash": hashlib.sha256(
                    row.implementation_steps.encode()
                ).hexdigest(),
                "success_criteria_hash": hashlib.sha256(row.success_criteria.encode()).hexdigest(),
                "activity_kind": row.activity_kind,
                "readiness_required": row.readiness_required,
                "responsible_role": row.responsible_role,
                "expected_output_hash": hashlib.sha256(row.expected_output.encode()).hexdigest(),
                "evidence_expectations_hash": hashlib.sha256(
                    row.evidence_expectations.encode()
                ).hexdigest(),
            }
        )
    else:
        values.update(
            {
                "acceptance_criteria_hash": hashlib.sha256(
                    row.acceptance_criteria.encode()
                ).hexdigest(),
                "evidence_type": row.evidence_type,
                "mandatory": row.mandatory,
            }
        )
    return values


def _record_audit(
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: QMSControlActivity | QMSControlEvidenceRequirement,
    action: str,
    old_values: dict[str, object] | None,
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
        old_values=old_values,
        new_values=_audit_values(row),
    )


def _persist[T: QMSControlActivity | QMSControlEvidenceRequirement](
    db: Session,
    row: T,
    actor: OrganizationActor,
    request_id: UUID,
    action: str,
    old: dict[str, object] | None,
) -> T:
    try:
        db.add(row)
        db.flush()
        _record_audit(db, actor, request_id, row, action, old)
        db.commit()
    except DBAPIError as error:
        db.rollback()
        original = error.orig
        detail = original.args[0] if original is not None and original.args else None
        state = detail.get("C") if isinstance(detail, dict) else None
        if state in {"23503", "23505", "23514", "40P01", "55P03"}:
            raise HTTPException(409, "definition, control, state or version conflicts") from None
        if state == "42501":
            raise HTTPException(403, "control authority denied") from None
        raise error
    except Exception:
        db.rollback()
        raise
    return row


def _new_values(
    control: QMSControl, actor: OrganizationActor, body: BaseModel
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "tenant_id": actor.tenant_id,
        "unit_id": control.unit_id,
        "process_id": control.process_id,
        "control_id": control.id,
        **body.model_dump(),
        "active": True,
        "row_version": 1,
        "created_by_user_id": actor.user_id,
        "created_at": now,
        "updated_at": now,
    }


def _update_definition[T: QMSControlActivity | QMSControlEvidenceRequirement](
    db: Session,
    actor: OrganizationActor,
    request_id: UUID,
    row: T | None,
    body: ActivityPatch | EvidenceRequirementPatch,
    resource: str,
) -> T:
    if row is None:
        raise HTTPException(404, "definition not found")
    require_capability(db, "controls.manage", row.unit_id)
    if row.row_version != body.expected_version:
        raise HTTPException(409, "definition changed; refresh before editing")
    _control(db, actor, row.control_id, manage=True)
    changes = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(422, "provide non-null definition changes")
    old = _audit_values(row)
    was_active = row.active
    for key, value in changes.items():
        setattr(row, key, value)
    row.row_version += 1
    row.updated_at = datetime.now(UTC)
    suffix = "deactivated" if was_active and row.active is False else "updated"
    return _persist(db, row, actor, request_id, f"control.{resource}_{suffix}", old)


@router.get("/controls/{control_id}/activities", response_model=list[ActivityResponse])
def list_activities(
    control_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=100),
) -> list[QMSControlActivity]:
    actor = actor_context(db, authenticated)
    control = _control(db, actor, control_id, manage=False)
    query = select(QMSControlActivity).where(
        QMSControlActivity.control_id == control.id,
        QMSControlActivity.tenant_id == actor.tenant_id,
        QMSControlActivity.unit_id == control.unit_id,
    )
    if not include_inactive:
        query = query.where(QMSControlActivity.active.is_(True))
    return list(
        db.scalars(query.order_by(QMSControlActivity.sequence, QMSControlActivity.id).limit(limit))
    )


@router.post(
    "/controls/{control_id}/activities",
    response_model=ActivityResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_activity(
    control_id: UUID,
    request: Request,
    body: ActivityInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlActivity:
    actor = actor_context(db, authenticated)
    control = _control(db, actor, control_id, manage=True)
    row = QMSControlActivity(**_new_values(control, actor, body))
    return _persist(db, row, actor, request.state.request_id, "control.activity_created", None)


@router.patch(
    "/control-activities/{activity_id}",
    response_model=ActivityResponse,
    dependencies=[Depends(require_csrf)],
)
def update_activity(
    activity_id: UUID,
    request: Request,
    body: ActivityPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlActivity:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSControlActivity)
        .where(
            QMSControlActivity.id == activity_id, QMSControlActivity.tenant_id == actor.tenant_id
        )
        .with_for_update()
    )
    return _update_definition(db, actor, request.state.request_id, row, body, "activity")


@router.get(
    "/controls/{control_id}/evidence-requirements", response_model=list[EvidenceRequirementResponse]
)
def list_evidence_requirements(
    control_id: UUID,
    db: DBSession,
    authenticated: Authenticated,
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=100),
) -> list[QMSControlEvidenceRequirement]:
    actor = actor_context(db, authenticated)
    control = _control(db, actor, control_id, manage=False)
    query = select(QMSControlEvidenceRequirement).where(
        QMSControlEvidenceRequirement.control_id == control.id,
        QMSControlEvidenceRequirement.tenant_id == actor.tenant_id,
        QMSControlEvidenceRequirement.unit_id == control.unit_id,
    )
    if not include_inactive:
        query = query.where(QMSControlEvidenceRequirement.active.is_(True))
    return list(
        db.scalars(
            query.order_by(
                QMSControlEvidenceRequirement.sequence, QMSControlEvidenceRequirement.id
            ).limit(limit)
        )
    )


@router.post(
    "/controls/{control_id}/evidence-requirements",
    response_model=EvidenceRequirementResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_evidence_requirement(
    control_id: UUID,
    request: Request,
    body: EvidenceRequirementInput,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlEvidenceRequirement:
    actor = actor_context(db, authenticated)
    control = _control(db, actor, control_id, manage=True)
    row = QMSControlEvidenceRequirement(**_new_values(control, actor, body))
    return _persist(
        db, row, actor, request.state.request_id, "control.evidence_requirement_created", None
    )


@router.patch(
    "/control-evidence-requirements/{requirement_id}",
    response_model=EvidenceRequirementResponse,
    dependencies=[Depends(require_csrf)],
)
def update_evidence_requirement(
    requirement_id: UUID,
    request: Request,
    body: EvidenceRequirementPatch,
    db: DBSession,
    authenticated: Authenticated,
) -> QMSControlEvidenceRequirement:
    actor = actor_context(db, authenticated)
    row = db.scalar(
        select(QMSControlEvidenceRequirement)
        .where(
            QMSControlEvidenceRequirement.id == requirement_id,
            QMSControlEvidenceRequirement.tenant_id == actor.tenant_id,
        )
        .with_for_update()
    )
    return _update_definition(
        db, actor, request.state.request_id, row, body, "evidence_requirement"
    )
