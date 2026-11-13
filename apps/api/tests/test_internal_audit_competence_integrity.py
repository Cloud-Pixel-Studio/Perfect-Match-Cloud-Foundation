# ruff: noqa: E501 -- controlled SQL fixtures/assertions in disposable PostgreSQL.
"""Traceable human competence reviews; synthetic document fixtures, never AV/S3 proof."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from typing import Any, Self
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_internal_audit_agenda_integrity import person
from test_internal_audit_agenda_integrity import records as records
from test_internal_audit_independence_integrity import Plan
from test_internal_audit_independence_integrity import plan as plan
from test_internal_audit_integrity import (
    AUDITOR,
    MANAGER,
    OWNER,
    REVIEWER,
    TENANT_A,
    TENANT_B,
    UNIT_A,
    UNIT_A_OTHER,
    UNIT_B,
    _actor,
    _authenticated,
    _engine,
    _grant,
    _request,
)
from test_internal_audit_integrity import planning_records as planning_records
from test_internal_audit_integrity import seed_identity as seed_identity

from pmc_api import audit_service
from pmc_api import internal_audit_agenda as agenda
from pmc_api import internal_audit_competence as competence
from pmc_api import internal_audit_independence as independence
from pmc_api import internal_audit_team as team
from pmc_api.database import set_request_context
from pmc_api.internal_audits import (
    InternalAuditPatch,
    InternalAuditTransition,
    get_audit,
    transition_audit,
    update_audit,
)
from pmc_api.models import QMSAuditCompetenceReview
from pmc_api.organization_service import OrganizationActor
from pmc_api.processes import ProcessInput, create_process
from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


@dataclass
class Source:
    document_id: UUID
    revision_id: UUID
    code: str


@dataclass
class Case:
    plan: Plan
    source: Source
    valid_until: date


def document_source(
    x: Plan,
    *,
    unit: UUID = UNIT_A,
    tenant: UUID = TENANT_A,
    document_status: str = "active",
    revision_status: str = "active",
    file_state: str = "clean",
) -> Source:
    """Use the real process service, then synthetic released-file metadata in the isolated DB.

    Scanning/storage/release workflows are covered elsewhere. This fixture exercises
    scope, source validity and immutable snapshots, and does not claim an AV verdict.
    """
    db = x.records.r.db
    set_request_context(db, user_id=OWNER, tenant_id=tenant)
    exists = db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE user_id=:user AND unit_id=:unit "
            "AND capability='processes.manage' AND status='active'"
        ),
        {"user": MANAGER, "unit": unit},
    )
    if not exists:
        create_grant(
            db,
            OrganizationActor(OWNER, str(OWNER), "owner", tenant),
            uuid4(),
            GrantInput(user_id=MANAGER, unit_id=unit, capability="processes.manage"),
        )
    set_request_context(db, user_id=MANAGER, tenant_id=tenant)
    process = create_process(
        db,
        OrganizationActor(MANAGER, str(MANAGER), "member", tenant),
        uuid4(),
        ProcessInput(unit_id=unit, code="COMP-" + uuid4().hex[:12], name="Auditor qualification"),
    )
    source = Source(uuid4(), uuid4(), "COMP-DOC-" + uuid4().hex[:10])
    now = datetime.now(UTC)
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("""
INSERT INTO qms_documents(id,tenant_id,unit_id,process_id,code,title,document_type,
 owner_user_id,status,current_revision_id,row_version,created_by_user_id,created_at,updated_at)
VALUES(:id,:tenant,:unit,:process,:code,'Auditor receiving training proof','other',NULL,
 :status,NULL,1,:actor,:now,:now)
"""),
            {
                "id": source.document_id,
                "tenant": tenant,
                "unit": unit,
                "process": process.id,
                "code": source.code,
                "status": document_status,
                "actor": MANAGER,
                "now": now,
            },
        )
        connection.execute(
            text("""
INSERT INTO qms_document_revisions(id,tenant_id,document_id,revision,status,
 prepared_by_user_id,reviewed_by_user_id,approved_by_user_id,change_summary,
 revision_date,effective_date,review_date,file_state,file_object_key,file_sha256,
 file_size,file_media_type,row_version,created_at)
VALUES(:id,:tenant,:document,'A',:status,:actor,:reviewer,:reviewer,'Synthetic reviewed source',
 :date,:date,NULL,:file_state,'private/synthetic-competence-proof.pdf',:hash,100,
 'application/pdf',1,:now)
"""),
            {
                "id": source.revision_id,
                "tenant": tenant,
                "document": source.document_id,
                "status": revision_status,
                "actor": MANAGER,
                "reviewer": OWNER,
                "date": now.date(),
                "file_state": file_state,
                "hash": "a" * 64,
                "now": now,
            },
        )
    return source


@pytest.fixture
def case(plan: Plan) -> Iterator[Case]:
    _grant(plan.records.r.db, REVIEWER, "documents.read")
    source = document_source(plan)
    parent = get_audit(plan.parent, plan.records.r.db, _authenticated(MANAGER))
    valid_until = max(parent.planned_end, datetime.now(UTC).date()) + timedelta(days=365)
    try:
        yield Case(plan, source, valid_until)
    finally:
        plan.records.r.db.rollback()
        # Only the harness-created disposable database receives these fixture resets.
        # Remove document FKs before the next module reseeds the synthetic identities.
        with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE qms_audit_competence_reviews, qms_document_revisions, "
                    "qms_documents CASCADE"
                )
            )


def body(
    c: Case, version: int = 0, decision: str = "confirmed", **changes: Any
) -> competence.ReviewInput:
    confirmed = decision == "confirmed"
    return competence.ReviewInput.model_validate(
        {
            "expected_audit_version": c.plan.version,
            "expected_review_version": version,
            "team_member_id": c.plan.records.auditor,
            "decision": decision,
            "notes": "Reviewed training, experience and relevance to the planned receiving audit.",
            "competence_attested": confirmed,
            "document_id": c.source.document_id if confirmed else None,
            "document_revision_id": c.source.revision_id if confirmed else None,
            "valid_until": c.valid_until if confirmed else None,
            **changes,
        }
    )


def record(c: Case, version: int = 0, decision: str = "confirmed", **changes: Any) -> Any:
    return competence.create_review(
        c.plan.parent,
        body(c, version, decision, **changes),
        _request(),
        c.plan.records.r.db,
        _authenticated(REVIEWER),
    )


def summary(c: Case, **paging: Any) -> Any:
    return competence.get_competence(
        c.plan.parent, c.plan.records.r.db, _authenticated(REVIEWER), **paging
    )


def test_confirmation_records_source_and_subject_snapshots_without_plan_write(case: Case) -> None:
    c = case
    before = summary(c)
    assert before.planned_auditors == 1 and before.current_assessments == 0
    result = record(c)
    row = result.review
    assert result.audit_version == c.plan.version and row.review_version == 1
    assert row.source_audit_version == c.plan.version
    assert row.subject_user_id == AUDITOR and row.subject_name_snapshot == str(AUDITOR)
    assert row.reviewer_user_id == REVIEWER and row.reviewer_name_snapshot == str(REVIEWER)
    assert (
        row.document_id == c.source.document_id and row.document_revision_id == c.source.revision_id
    )
    assert row.document_code_snapshot == c.source.code and row.document_revision_snapshot == "A"
    assert row.file_sha256 == "a" * 64 and row.valid_until == c.valid_until
    current = summary(c)
    assert current.current_assessments == 1 and current.auditors[0].review_current
    assert current.auditors[0].assessment_status == "current"
    assert (
        get_audit(c.plan.parent, c.plan.records.r.db, _authenticated(MANAGER)).row_version
        == c.plan.version
    )
    diagnostic = independence.get_independence(
        c.plan.parent, c.plan.records.r.db, _authenticated(REVIEWER)
    )
    assert not diagnostic.ready_for_execution
    assert {check.code: check.status for check in diagnostic.checks}["competence"] == "passed"
    set_request_context(c.plan.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    event = c.plan.records.r.db.execute(
        text("SELECT new_values FROM audit_events WHERE new_values->>'competence_review_id'=:id"),
        {"id": str(row.id)},
    ).scalar_one()
    assert event["competence_notes_hash"] == hashlib.sha256(row.notes.encode()).hexdigest()
    assert "notes" not in event and row.notes not in str(event)


def test_withdrawal_appends_history_preserves_evidence_and_hashes_actual_decisions(
    case: Case,
) -> None:
    original = record(case).review
    reason = "New information requires a renewed assessment."
    withdrawn = record(case, 1, "withdrawn", notes=reason).review
    assert withdrawn.review_version == 2 and not withdrawn.competence_attested
    for field in [
        "document_id",
        "document_revision_id",
        "document_code_snapshot",
        "file_sha256",
        "valid_until",
        "subject_user_id",
    ]:
        assert getattr(withdrawn, field) == getattr(original, field)
    assert summary(case).current_assessments == 0
    assert summary(case).auditors[0].assessment_status == "withdrawn"
    rows = competence.list_reviews(
        case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
    )
    assert [row.review_version for row in rows] == [2, 1]
    set_request_context(case.plan.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    event = case.plan.records.r.db.execute(
        text(
            "SELECT old_values,new_values FROM audit_events WHERE new_values->>'competence_review_id'=:id"
        ),
        {"id": str(withdrawn.id)},
    ).one()
    assert (
        event.old_values["competence_notes_hash"]
        == hashlib.sha256(original.notes.encode()).hexdigest()
    )
    assert event.new_values["competence_notes_hash"] == hashlib.sha256(reason.encode()).hexdigest()
    with pytest.raises(HTTPException) as repeated:
        record(case, 2, "withdrawn")
    assert repeated.value.status_code == 409


def test_plan_change_marks_assessment_outdated_and_requires_current_expected_version(
    case: Case,
) -> None:
    record(case)
    x = case.plan
    changed = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=x.version, objective="Revised sampling scope"),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    assert summary(case).auditors[0].assessment_status == "outdated"
    assert summary(case).current_assessments == 0
    with pytest.raises(HTTPException) as stale:
        record(case, 1)
    assert stale.value.status_code == 409
    x.version = changed.row_version
    assert record(case, 1).review.source_audit_version == x.version
    assert summary(case).current_assessments == 1


def test_stale_history_and_withdrawal_without_assessment_never_duplicate(case: Case) -> None:
    with pytest.raises(HTTPException) as missing:
        record(case, decision="withdrawn")
    assert missing.value.status_code == 409
    record(case)
    with pytest.raises(HTTPException) as stale:
        record(case)
    assert stale.value.status_code == 409
    assert (
        len(
            competence.list_reviews(
                case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
            )
        )
        == 1
    )


def test_document_read_revocation_hides_existing_history_and_prevents_new_decisions(
    case: Case,
) -> None:
    record(case)
    db = case.plan.records.r.db
    set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
    grant = db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE user_id=:user AND unit_id=:unit AND capability='documents.read' AND status='active'"
        ),
        {"user": REVIEWER, "unit": UNIT_A},
    )
    assert grant
    revoke_grant(db, _actor(OWNER, "owner"), uuid4(), grant)
    actions: list[Callable[[], Any]] = [lambda: summary(case), lambda: record(case, 1)]
    for action in actions:
        with pytest.raises(HTTPException) as revoked:
            action()
        assert revoked.value.status_code == 403
        db.rollback()
    set_request_context(db, user_id=REVIEWER, tenant_id=TENANT_A)
    assert db.scalar(text("SELECT count(*) FROM qms_audit_competence_reviews")) == 0
    diagnostic = independence.get_independence(case.plan.parent, db, _authenticated(REVIEWER))
    assert {check.code: check.status for check in diagnostic.checks}["competence"] == "unverified"


def test_creator_cannot_self_review_even_with_explicit_review_and_document_access(
    case: Case,
) -> None:
    _grant(case.plan.records.r.db, MANAGER, "documents.read")
    _grant(case.plan.records.r.db, MANAGER, "audits.review")
    with pytest.raises(HTTPException) as self_review:
        competence.create_review(
            case.plan.parent,
            body(case),
            _request(),
            case.plan.records.r.db,
            _authenticated(MANAGER),
        )
    assert self_review.value.status_code == 409
    assert summary(case).review_version == 0


def test_read_and_document_access_never_imply_review_authority(case: Case) -> None:
    _grant(case.plan.records.r.db, AUDITOR, "documents.read")
    read = competence.get_competence(
        case.plan.parent, case.plan.records.r.db, _authenticated(AUDITOR)
    )
    assert not read.can_review
    with pytest.raises(HTTPException) as denied:
        competence.create_review(
            case.plan.parent,
            body(case),
            _request(),
            case.plan.records.r.db,
            _authenticated(AUDITOR),
        )
    assert denied.value.status_code == 403


@pytest.mark.parametrize("unit,tenant", [(UNIT_A_OTHER, TENANT_A), (UNIT_B, TENANT_B)])
def test_document_source_must_be_in_the_same_unit_and_company(
    case: Case, unit: UUID, tenant: UUID
) -> None:
    other = document_source(case.plan, unit=unit, tenant=tenant)
    with pytest.raises(HTTPException) as denied:
        record(case, document_id=other.document_id, document_revision_id=other.revision_id)
    assert denied.value.status_code == 409
    choices = competence.list_documents(
        case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
    )
    assert all(choice.document_id != other.document_id for choice in choices)


@pytest.mark.parametrize(
    "document_status,revision_status,file_state",
    [
        ("active", "draft", "clean"),
        ("active", "under_review", "quarantined"),
        ("obsolete", "active", "clean"),
    ],
)
def test_only_clean_released_sources_are_accepted(
    case: Case, document_status: str, revision_status: str, file_state: str
) -> None:
    unsafe = document_source(
        case.plan,
        document_status=document_status,
        revision_status=revision_status,
        file_state=file_state,
    )
    with pytest.raises(HTTPException) as rejected:
        record(case, document_id=unsafe.document_id, document_revision_id=unsafe.revision_id)
    assert rejected.value.status_code == 409
    choices = competence.list_documents(
        case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
    )
    assert all(choice.document_id != unsafe.document_id for choice in choices)


def test_validity_must_cover_today_and_the_complete_planned_audit(case: Case) -> None:
    parent = get_audit(case.plan.parent, case.plan.records.r.db, _authenticated(MANAGER))
    for expiry in [
        datetime.now(UTC).date() - timedelta(days=1),
        parent.planned_end - timedelta(days=1),
    ]:
        with pytest.raises(HTTPException) as expired:
            record(case, valid_until=expiry)
        assert expired.value.status_code == 409
        case.plan.records.r.db.rollback()
    assert summary(case).review_version == 0


def test_auditees_are_not_targets_for_a_competence_confirmation(case: Case) -> None:
    with pytest.raises(HTTPException) as wrong_role:
        record(case, team_member_id=case.plan.records.auditee)
    assert wrong_role.value.status_code == 409


def test_obsoleting_support_invalidates_the_projection_but_allows_reasoned_withdrawal(
    case: Case,
) -> None:
    record(case)
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as db:
        db.execute(
            text(
                "UPDATE qms_documents SET status='obsolete',row_version=row_version+1,updated_at=CURRENT_TIMESTAMP WHERE id=:id"
            ),
            {"id": case.source.document_id},
        )
    current = summary(case)
    assert (
        current.current_assessments == 0
        and current.auditors[0].assessment_status == "evidence_unavailable"
    )
    with pytest.raises(HTTPException) as source:
        record(case, 1)
    assert source.value.status_code == 409
    assert record(case, 1, "withdrawn").review.decision == "withdrawn"


def test_inactive_subject_invalidates_current_status_but_can_be_withdrawn(case: Case) -> None:
    record(case)
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    try:
        with admin.begin() as db:
            db.execute(
                text(
                    "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": AUDITOR},
            )
        current = summary(case)
        assert (
            current.current_assessments == 0
            and current.auditors[0].assessment_status == "member_inactive"
        )
        with pytest.raises(HTTPException) as inactive:
            record(case, 1)
        assert inactive.value.status_code == 409
        assert record(case, 1, "withdrawn").review.decision == "withdrawn"
    finally:
        with admin.begin() as db:
            db.execute(
                text(
                    "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": AUDITOR},
            )
        admin.dispose()


def test_retired_assignments_remain_in_history_and_can_be_withdrawn(case: Case) -> None:
    record(case)
    x = case.plan
    current = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=x.version, lead_auditor_user_id=None),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    x.version = current.row_version
    activity = agenda.list_agenda(x.parent, x.records.r.db, _authenticated(MANAGER))[0]
    result = agenda.withdraw_agenda_item(
        x.parent,
        activity.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=x.version,
            expected_version=activity.row_version,
            reason="Participant no longer assigned",
        ),
        _request(),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    x.version = result.audit_version
    auditor = next(
        row
        for row in team.list_team_members(x.parent, x.records.r.db, _authenticated(MANAGER))
        if row.id == x.records.auditor
    )
    retired = team.withdraw_team_member(
        x.parent,
        auditor.id,
        team.TeamWithdrawal(
            expected_audit_version=x.version,
            expected_version=auditor.row_version,
            reason="Replaced auditor assignment",
        ),
        _request(),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    x.version = retired.audit_version
    current = summary(case)
    assert current.planned_auditors == 0 and current.current_assessments == 0
    assert current.auditors[0].team_member_id == x.records.auditor
    assert (
        not current.auditors[0].assignment_active
        and current.auditors[0].assessment_status == "assignment_inactive"
    )
    assert record(case, 1, "withdrawn").review.decision == "withdrawn"


def test_runtime_cannot_rewrite_or_remove_competence_history(case: Case) -> None:
    row = record(case).review
    for sql in [
        "UPDATE qms_audit_competence_reviews SET notes='rewrite' WHERE id=:id",
        "DELETE FROM qms_audit_competence_reviews WHERE id=:id",
        "TRUNCATE qms_audit_competence_reviews",
    ]:
        set_request_context(case.plan.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError) as denied:
            case.plan.records.r.db.execute(text(sql), {"id": row.id})
        assert denied.value.orig is not None
        case.plan.records.r.db.rollback()
    assert (
        len(
            competence.list_reviews(
                case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
            )
        )
        == 1
    )


def raw_review(c: Case, **changes: Any) -> QMSAuditCompetenceReview:
    return QMSAuditCompetenceReview(
        **{
            "id": uuid4(),
            "tenant_id": TENANT_A,
            "unit_id": UNIT_A,
            "audit_id": c.plan.parent,
            "team_member_id": c.plan.records.auditor,
            "subject_user_id": AUDITOR,
            "subject_name_snapshot": str(AUDITOR),
            "review_version": 1,
            "source_audit_version": c.plan.version,
            "decision": "confirmed",
            "notes": "Direct SQL policy check",
            "competence_attested": True,
            "document_id": c.source.document_id,
            "document_revision_id": c.source.revision_id,
            "document_code_snapshot": c.source.code,
            "document_title_snapshot": "Auditor receiving training proof",
            "document_revision_snapshot": "A",
            "file_sha256": "a" * 64,
            "valid_until": c.valid_until,
            "reviewer_user_id": REVIEWER,
            "reviewer_name_snapshot": str(REVIEWER),
            "created_at": datetime.now(UTC),
            **changes,
        }
    )


def test_runtime_sql_independently_rejects_actor_plan_sequence_and_scope_forgery(
    case: Case,
) -> None:
    db = case.plan.records.r.db
    cases: list[dict[str, Any]] = [
        {"reviewer_user_id": MANAGER},
        {"reviewer_name_snapshot": "Forged reviewer"},
        {"subject_user_id": MANAGER},
        {"source_audit_version": case.plan.version - 1},
        {"review_version": 2},
        {"unit_id": UNIT_A_OTHER},
        {"document_id": uuid4()},
    ]
    for change in cases:
        set_request_context(db, user_id=REVIEWER, tenant_id=TENANT_A)
        db.add(raw_review(case, **change))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
    assert competence.list_reviews(case.plan.parent, db, _authenticated(REVIEWER)) == []


def test_document_and_name_snapshots_are_picked_by_server_not_sql_client(case: Case) -> None:
    db = case.plan.records.r.db
    set_request_context(db, user_id=REVIEWER, tenant_id=TENANT_A)
    row = raw_review(
        case,
        document_code_snapshot="Forged code",
        document_title_snapshot="Forged source",
        document_revision_snapshot="Z",
        file_sha256="b" * 64,
        subject_name_snapshot="Forged subject",
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    assert row.document_code_snapshot == case.source.code and row.document_revision_snapshot == "A"
    assert row.file_sha256 == "a" * 64
    assert row.subject_name_snapshot == str(AUDITOR) and row.reviewer_name_snapshot == str(REVIEWER)
    db.rollback()  # Do not commit a direct-SQL fixture outside the API's atomic event command.
    assert competence.list_reviews(case.plan.parent, db, _authenticated(REVIEWER)) == []


def test_unknown_and_foreign_audit_reads_do_not_disclose_the_competence_roster(case: Case) -> None:
    for audit_id in [
        uuid4(),
        case.plan.records.r.audits[UNIT_A_OTHER][0].id,
        case.plan.records.r.audits[UNIT_B][0].id,
    ]:
        with pytest.raises(HTTPException) as missing:
            competence.get_competence(audit_id, case.plan.records.r.db, _authenticated(REVIEWER))
        assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as foreign:
        competence.get_competence(
            case.plan.parent, case.plan.records.r.db, _authenticated(MANAGER, TENANT_B)
        )
    assert foreign.value.status_code == 404


def test_event_failure_rolls_back_the_review_and_does_not_advance_plan(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Synthetic competence ledger failure")

    monkeypatch.setattr(audit_service, "record_internal_audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic competence ledger failure"):
        record(case)
    assert (
        competence.list_reviews(case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER))
        == []
    )
    assert (
        get_audit(case.plan.parent, case.plan.records.r.db, _authenticated(MANAGER)).row_version
        == case.plan.version
    )


def test_global_review_version_serializes_concurrent_assessments(case: Case) -> None:
    case.plan.records.r.db.rollback()
    gate = Barrier(2, timeout=10)
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")

    def write() -> int:
        with Session(runtime) as db:
            gate.wait()
            try:
                competence.create_review(
                    case.plan.parent, body(case), _request(), db, _authenticated(REVIEWER)
                )
                return 201
            except HTTPException as conflict:
                db.rollback()
                return conflict.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write) for _ in range(2)]
            assert sorted(job.result(timeout=20) for job in futures) == [201, 409]
        assert (
            len(
                competence.list_reviews(
                    case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
                )
            )
            == 1
        )
    finally:
        runtime.dispose()


def test_summary_totals_cover_all_active_auditors_independently_of_the_page(case: Case) -> None:
    x = case.plan
    second = person(x.records.r, x.parent, MANAGER, "auditor")
    x.version = get_audit(x.parent, x.records.r.db, _authenticated(MANAGER)).row_version
    record(case)
    first_page = summary(case, limit=1, offset=0)
    second_page = summary(case, limit=1, offset=1)
    assert first_page.planned_auditors == second_page.planned_auditors == 2
    assert first_page.current_assessments == second_page.current_assessments == 1
    assert len(first_page.auditors) == len(second_page.auditors) == 1
    assert first_page.auditors[0].team_member_id != second_page.auditors[0].team_member_id
    record(case, 1, team_member_id=second)
    assert summary(case).current_assessments == 2
    empty_page = summary(case, limit=1, offset=1_000_000)
    assert empty_page.auditors == []
    assert empty_page.planned_auditors == empty_page.current_assessments == 2
    newest = competence.list_reviews(
        x.parent, x.records.r.db, _authenticated(REVIEWER), limit=1, offset=0
    )
    oldest = competence.list_reviews(
        x.parent, x.records.r.db, _authenticated(REVIEWER), limit=1, offset=1
    )
    assert newest[0].review_version == 2 and oldest[0].review_version == 1


def test_closed_audit_cannot_receive_new_competence_decisions(case: Case) -> None:
    record(case)
    x = case.plan
    closed = transition_audit(
        _request(),
        x.parent,
        InternalAuditTransition(
            expected_version=x.version, target_state="cancelled", decision="Withdrawn audit plan"
        ),
        x.records.r.db,
        _authenticated(REVIEWER),
    )
    x.version = closed.row_version
    assert summary(case).current_assessments == 0
    with pytest.raises(HTTPException) as locked:
        record(case, 1)
    assert locked.value.status_code == 409


def test_input_requires_evidence_date_reason_attestation_and_no_forged_identity() -> None:
    base = {
        "expected_audit_version": 1,
        "expected_review_version": 0,
        "team_member_id": uuid4(),
        "decision": "confirmed",
        "notes": "Reviewed qualifications",
        "competence_attested": True,
        "document_id": uuid4(),
        "document_revision_id": uuid4(),
        "valid_until": datetime.now(UTC).date() + timedelta(days=365),
    }
    cases: list[dict[str, Any]] = [
        {"notes": " "},
        {"competence_attested": False},
        {"competence_attested": "true"},
        {"valid_until": None},
        {"document_id": None},
        {"document_revision_id": None},
        {"reviewer_user_id": str(REVIEWER)},
        {"tenant_id": str(TENANT_B)},
        {"decision": "withdrawn"},
    ]
    for changes in cases:
        with pytest.raises(ValidationError):
            competence.ReviewInput.model_validate({**base, **changes})


def test_expiry_is_rechecked_on_read_without_rewriting_the_immutable_assessment(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = record(case).review

    class LaterDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Self:
            return cls.combine(
                case.valid_until + timedelta(days=1), datetime.min.time(), tzinfo=UTC
            )

    monkeypatch.setattr(competence, "datetime", LaterDateTime)
    current = summary(case)
    assert current.current_assessments == 0
    assert current.auditors[0].assessment_status == "expired"
    assert current.auditors[0].latest_review.id == original.id
    assert current.auditors[0].latest_review.valid_until == original.valid_until
    assert (
        len(
            competence.list_reviews(
                case.plan.parent, case.plan.records.r.db, _authenticated(REVIEWER)
            )
        )
        == 1
    )


def test_inactive_signer_is_distinct_from_active_subject_and_invalidates_current_projection(
    case: Case,
) -> None:
    record(case)
    _grant(case.plan.records.r.db, AUDITOR, "documents.read")
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    try:
        with admin.begin() as db:
            db.execute(
                text(
                    "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": REVIEWER},
            )
        current = competence.get_competence(
            case.plan.parent, case.plan.records.r.db, _authenticated(AUDITOR)
        )
        assert current.current_assessments == 0
        assert current.auditors[0].member_active
        assert current.auditors[0].assessment_status == "reviewer_inactive"
    finally:
        with admin.begin() as db:
            db.execute(
                text(
                    "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": REVIEWER},
            )
        admin.dispose()


def test_summary_totals_and_page_share_one_snapshot_when_source_is_obsoleted_after_read(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(case)
    db = case.plan.records.r.db
    original = db.execute
    changed = False

    def obsolete_after_materialization(statement: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal changed
        result = original(statement, *args, **kwargs)
        if not changed and "from totals" in str(statement).lower():
            # Materialize the single SQL snapshot before the unrelated transaction
            # changes its source. Both aggregate and page must describe that snapshot.
            frozen = result.freeze()
            changed = True
            with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as admin:
                admin.execute(
                    text(
                        "UPDATE qms_documents SET status='obsolete',row_version=row_version+1,updated_at=CURRENT_TIMESTAMP WHERE id=:id"
                    ),
                    {"id": case.source.document_id},
                )
            return frozen()
        return result

    monkeypatch.setattr(db, "execute", obsolete_after_materialization)
    first = summary(case)
    assert changed and first.current_assessments == 1
    assert first.auditors[0].assessment_status == "current" and first.auditors[0].review_current
    second = summary(case)
    assert second.current_assessments == 0
    assert second.auditors[0].assessment_status == "evidence_unavailable"
    assert not second.auditors[0].review_current


def test_audit_read_revoked_after_summary_materialization_returns_access_denial(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(case)
    db = case.plan.records.r.db
    set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
    grant = db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE user_id=:user AND unit_id=:unit AND capability='audits.read' AND status='active'"
        ),
        {"user": REVIEWER, "unit": UNIT_A},
    )
    assert grant
    db.rollback()
    original = db.execute
    revoked = False
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")

    def revoke_after_materialization(statement: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal revoked
        result = original(statement, *args, **kwargs)
        if not revoked and "from totals" in str(statement).lower():
            frozen = result.freeze()
            revoked = True
            with Session(runtime) as other:
                set_request_context(other, user_id=OWNER, tenant_id=TENANT_A)
                revoke_grant(other, _actor(OWNER, "owner"), uuid4(), grant)
            return frozen()
        return result

    monkeypatch.setattr(db, "execute", revoke_after_materialization)
    try:
        with pytest.raises(HTTPException) as denied:
            summary(case)
        assert revoked and denied.value.status_code in {403, 404}
    finally:
        runtime.dispose()
