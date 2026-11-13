from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class QMSAccessGrant(Base):
    __tablename__ = "qms_access_grants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QMSAuditProgram(Base):
    __tablename__ = "qms_audit_programs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    cancellation_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSInternalAudit(Base):
    __tablename__ = "qms_internal_audits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    program_id: Mapped[UUID | None] = mapped_column()
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    lead_auditor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    independence_status: Mapped[str] = mapped_column(String(24), nullable=False)
    independence_notes: Mapped[str] = mapped_column(Text, nullable=False)
    independence_reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    independence_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    cancellation_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSAuditScope(Base):
    __tablename__ = "qms_audit_scopes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    process_id: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    withdrawal_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    withdrawn_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSAuditIndependenceReview(Base):
    __tablename__ = "qms_audit_independence_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_audit_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    independence_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewer_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    lead_auditor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSAuditAgendaItem(Base):
    __tablename__ = "qms_audit_agenda_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str] = mapped_column(String(240), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column()
    auditor_team_member_id: Mapped[UUID] = mapped_column(nullable=False)
    auditee_team_member_id: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    withdrawal_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    withdrawn_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSAuditTeamMember(Base):
    __tablename__ = "qms_audit_team_members"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    team_role: Mapped[str] = mapped_column(String(20), nullable=False)
    responsibilities: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    withdrawal_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    withdrawn_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSAuditCriterion(Base):
    __tablename__ = "qms_audit_criteria"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(240), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    withdrawal_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    withdrawn_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSProcess(Base):
    __tablename__ = "qms_processes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column()
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    process_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[str] = mapped_column(Text, nullable=False)
    outputs: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSProcessSite(Base):
    __tablename__ = "qms_process_sites"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    process_id: Mapped[UUID] = mapped_column(primary_key=True)
    process_unit_id: Mapped[UUID] = mapped_column(nullable=False)
    site_unit_id: Mapped[UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControl(Base):
    __tablename__ = "qms_controls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    guidance_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    guidance_why: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_steps: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_tools: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    practical_notes: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControlInstance(Base):
    __tablename__ = "qms_control_instances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    implementation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    applicability: Mapped[str] = mapped_column(String(20), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    implementation_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControlActivity(Base):
    __tablename__ = "qms_control_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_steps: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    activity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    readiness_required: Mapped[bool] = mapped_column(nullable=False)
    responsible_role: Mapped[str] = mapped_column(String(160), nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_expectations: Mapped[str] = mapped_column(Text, nullable=False)
    definition_key: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControlEvidenceRequirement(Base):
    __tablename__ = "qms_control_evidence_requirements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(24), nullable=False)
    mandatory: Mapped[bool] = mapped_column(nullable=False)
    definition_key: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControlInstanceActivity(Base):
    __tablename__ = "qms_control_instance_activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)
    activity_definition_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_steps: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    activity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    readiness_required: Mapped[bool] = mapped_column(nullable=False)
    responsible_role: Mapped[str] = mapped_column(String(160), nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_expectations: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    completion_summary: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSControlInstanceEvidence(Base):
    __tablename__ = "qms_control_instance_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    control_id: Mapped[UUID] = mapped_column(nullable=False)
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)
    requirement_definition_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(24), nullable=False)
    mandatory: Mapped[bool] = mapped_column(nullable=False)
    document_id: Mapped[UUID | None] = mapped_column()
    document_revision_id: Mapped[UUID | None] = mapped_column()
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_decision: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSCAPA(Base):
    __tablename__ = "qms_capas"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ncr_id: Mapped[UUID | None] = mapped_column()
    source_risk_id: Mapped[UUID | None] = mapped_column()
    source_code: Mapped[str] = mapped_column(String(40), nullable=False)
    source_state: Mapped[str] = mapped_column(String(24), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_date: Mapped[date | None] = mapped_column(Date)
    root_cause_method: Mapped[str | None] = mapped_column(String(20))
    analysis_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    analysis_summary: Mapped[str] = mapped_column(Text, nullable=False)
    verified_root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    other_method_name: Mapped[str] = mapped_column(String(160), nullable=False)
    analysis_started_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    analysis_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan_summary: Mapped[str] = mapped_column(Text, nullable=False)
    planned_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    implementation_started_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    implementation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_started_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_notes: Mapped[str] = mapped_column(Text, nullable=False)
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSCAPAAction(Base):
    __tablename__ = "qms_capa_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    capa_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str] = mapped_column(Text, nullable=False)
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSCAPAEffectivenessReview(Base):
    __tablename__ = "qms_capa_effectiveness_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    capa_id: Mapped[UUID] = mapped_column(nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    implementation_started_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    implementation_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    review_started_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    review_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active_action_count: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_action_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cancelled_action_count: Mapped[int] = mapped_column(Integer, nullable=False)


class QMSCAPADocumentLink(Base):
    __tablename__ = "qms_capa_document_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    capa_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    document_revision_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_revision: Mapped[str] = mapped_column(String(40), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_process_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_code: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str] = mapped_column(Text, nullable=False)


class CAPATraceLinkFields:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    capa_id: Mapped[UUID] = mapped_column(nullable=False)
    target_process_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_code: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str] = mapped_column(Text, nullable=False)


class QMSCAPAControlLink(CAPATraceLinkFields, Base):
    __tablename__ = "qms_capa_control_links"
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSCAPAEvidenceLink(CAPATraceLinkFields, Base):
    __tablename__ = "qms_capa_evidence_links"
    evidence_id: Mapped[UUID] = mapped_column(nullable=False)
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSNonconformity(Base):
    __tablename__ = "qms_nonconformities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_date: Mapped[date] = mapped_column(Date, nullable=False)
    detected_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    containment_required: Mapped[bool] = mapped_column(nullable=False)
    containment_action: Mapped[str] = mapped_column(Text, nullable=False)
    containment_owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    containment_date: Mapped[date | None] = mapped_column(Date)
    containment_completed: Mapped[bool] = mapped_column(nullable=False)
    disposition: Mapped[str | None] = mapped_column(String(24))
    disposition_notes: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_summary: Mapped[str] = mapped_column(Text, nullable=False)
    closure_notes: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    cancellation_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    opened_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NCRLinkFields:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    nonconformity_id: Mapped[UUID] = mapped_column(nullable=False)
    target_process_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_code: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str] = mapped_column(Text, nullable=False)


class QMSNCRRiskLink(NCRLinkFields, Base):
    __tablename__ = "qms_ncr_risk_links"
    risk_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSNCRControlLink(NCRLinkFields, Base):
    __tablename__ = "qms_ncr_control_links"
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSNCREvidenceLink(NCRLinkFields, Base):
    __tablename__ = "qms_ncr_evidence_links"
    evidence_id: Mapped[UUID] = mapped_column(nullable=False)
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSNCRDocumentLink(NCRLinkFields, Base):
    __tablename__ = "qms_ncr_document_links"
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    document_revision_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_revision: Mapped[str] = mapped_column(String(40), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class QMSRisk(Base):
    __tablename__ = "qms_risks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cause: Mapped[str] = mapped_column(Text, nullable=False)
    potential_effect: Mapped[str] = mapped_column(Text, nullable=False)
    benefit: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_action: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation_plan: Mapped[str] = mapped_column(Text, nullable=False)
    closure_notes: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    response_strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_model: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold_moderate: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_high: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_critical: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskLinkFields:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    risk_id: Mapped[UUID] = mapped_column(nullable=False)
    target_process_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_code: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    linked_target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str] = mapped_column(Text, nullable=False)


class QMSRiskControlLink(RiskLinkFields, Base):
    __tablename__ = "qms_risk_control_links"
    control_instance_id: Mapped[UUID] = mapped_column(nullable=False)


class QMSRiskDocumentLink(RiskLinkFields, Base):
    __tablename__ = "qms_risk_document_links"
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    document_revision_id: Mapped[UUID] = mapped_column(nullable=False)
    snapshot_revision: Mapped[str] = mapped_column(String(40), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class QMSDocument(Base):
    __tablename__ = "qms_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    process_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_revision_id: Mapped[UUID | None] = mapped_column()
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QMSDocumentRevision(Base):
    __tablename__ = "qms_document_revisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    revision: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    prepared_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revision_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    file_state: Mapped[str] = mapped_column(String(20), nullable=False, default="missing")
    file_object_key: Mapped[str | None] = mapped_column(String(300))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int | None] = mapped_column(Integer)
    file_media_type: Mapped[str | None] = mapped_column(String(120))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalIdentity(TimestampMixin, Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id"),
        CheckConstraint("role IN ('owner', 'admin', 'member', 'auditor')"),
        CheckConstraint("status IN ('active', 'revoked')"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class ApplicationSession(TimestampMixin, Base):
    __tablename__ = "application_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    current_tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id"))
    csrf_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OIDCLoginTransaction(TimestampMixin, Base):
    __tablename__ = "oidc_login_transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    state_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    login_binding_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    encrypted_pkce_verifier: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantIsolationProbe(TimestampMixin, Base):
    __tablename__ = "tenant_isolation_probes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(160), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column()
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    old_values: Mapped[dict[str, object] | None] = mapped_column(JSON)
    new_values: Mapped[dict[str, object] | None] = mapped_column(JSON)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class OrganizationUnit(TimestampMixin, Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id"),
        CheckConstraint("unit_type IN ('site', 'department', 'team')"),
        CheckConstraint("status IN ('active', 'archived')"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    parent_id: Mapped[UUID | None] = mapped_column()
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationUnitAssignment(TimestampMixin, Base):
    __tablename__ = "organization_unit_assignments"
    __table_args__ = (
        CheckConstraint("assignment_role IN ('member', 'lead')"),
        CheckConstraint("status IN ('active', 'inactive')"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignment_role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowDefinition(TimestampMixin, Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowVersion(TimestampMixin, Base):
    __tablename__ = "workflow_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    definition_id: Mapped[UUID] = mapped_column(nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowStep(TimestampMixin, Base):
    __tablename__ = "workflow_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    workflow_version_id: Mapped[UUID] = mapped_column(nullable=False)
    step_key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_start: Mapped[bool] = mapped_column(nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowTransition(TimestampMixin, Base):
    __tablename__ = "workflow_transitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    workflow_version_id: Mapped[UUID] = mapped_column(nullable=False)
    from_step_id: Mapped[UUID] = mapped_column(nullable=False)
    to_step_id: Mapped[UUID] = mapped_column(nullable=False)
    transition_key: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowStepAssignment(TimestampMixin, Base):
    __tablename__ = "workflow_step_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    workflow_version_id: Mapped[UUID] = mapped_column(nullable=False)
    step_id: Mapped[UUID] = mapped_column(nullable=False)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    target_organization_unit_id: Mapped[UUID | None] = mapped_column()
    target_application_role: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowInstance(TimestampMixin, Base):
    __tablename__ = "workflow_instances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    workflow_version_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_step_id: Mapped[UUID] = mapped_column(nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowInstanceEvent(Base):
    __tablename__ = "workflow_instance_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    instance_id: Mapped[UUID] = mapped_column(nullable=False)
    workflow_version_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_step_id: Mapped[UUID | None] = mapped_column()
    to_step_id: Mapped[UUID | None] = mapped_column()
    transition_id: Mapped[UUID | None] = mapped_column()
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    reason: Mapped[str | None] = mapped_column(String(500))
