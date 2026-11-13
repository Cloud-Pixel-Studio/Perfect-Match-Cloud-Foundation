"""Independent review history, stale-plan diagnostics and runtime isolation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_internal_audit_agenda_integrity import Records, person
from test_internal_audit_agenda_integrity import add as add_agenda
from test_internal_audit_agenda_integrity import records as records
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
    _authenticated,
    _grant,
    _request,
)
from test_internal_audit_integrity import planning_records as planning_records
from test_internal_audit_integrity import seed_identity as seed_identity

from pmc_api import audit_service
from pmc_api import internal_audit_criteria as criteria
from pmc_api import internal_audit_independence as independence
from pmc_api.database import set_request_context
from pmc_api.internal_audits import (
    InternalAuditPatch,
    InternalAuditTransition,
    get_audit,
    transition_audit,
    update_audit,
)

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


@dataclass
class Plan:
    records: Records
    parent: UUID
    version: int


@pytest.fixture
def plan(records: Records) -> Plan:
    x = records
    add_agenda(x)
    parent = get_audit(x.parent, x.r.db, _authenticated(MANAGER))
    criteria.create_criterion(
        x.parent,
        criteria.CriterionInput(
            expected_audit_version=parent.row_version,
            sequence=10,
            title="Receiving criterion",
            requirement="Evaluate controlled receiving records",
            source_type="internal",
            reference="RCV",
            scope_id=x.scope,
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    parent = get_audit(x.parent, x.r.db, _authenticated(MANAGER))
    parent = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=parent.row_version, lead_auditor_user_id=AUDITOR),
        x.r.db,
        _authenticated(MANAGER),
    )
    parent = transition_audit(
        _request(),
        x.parent,
        InternalAuditTransition(
            expected_version=parent.row_version,
            target_state="planned",
            decision="Schedule reviewed plan",
        ),
        x.r.db,
        _authenticated(MANAGER),
    )
    version = parent.row_version
    _grant(x.r.db, REVIEWER, "audits.read")
    _grant(x.r.db, REVIEWER, "audits.review")
    return Plan(x, x.parent, version)


def record(
    x: Plan, version: int = 0, decision: str = "confirmed", **changes: Any
) -> independence.ReviewResult:
    return independence.create_review(
        x.parent,
        independence.ReviewInput.model_validate(
            {
                "expected_audit_version": x.version,
                "expected_review_version": version,
                "decision": decision,
                "notes": "Process ownership and other relationships assessed by reviewer.",
                "independence_attested": decision != "withdrawn",
                **changes,
            }
        ),
        _request(),
        x.records.r.db,
        _authenticated(REVIEWER),
    )


def test_separate_reviewer_records_immutable_history_without_plan_write_or_execution(
    plan: Plan,
) -> None:
    x = plan
    summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
    assert summary.can_review and summary.review_version == 0 and not summary.ready_for_execution
    result = record(x)
    assert result.audit_version == x.version and result.review.review_version == 1
    assert result.review.reviewer_name_snapshot == str(REVIEWER)
    summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
    assert summary.review_current and not summary.ready_for_execution
    checks = {item.code: item.status for item in summary.checks}
    assert checks["independence"] == "passed" and checks["competence"] == "unverified"
    assert checks["execution_authority"] == "blocked" and checks["execution_workflow"] == "blocked"
    assert get_audit(x.parent, x.records.r.db, _authenticated(MANAGER)).row_version == x.version
    assert (
        record(
            x, 1, "override", notes="Documented exception and mitigation accepted."
        ).review.review_version
        == 2
    )
    assert (
        record(
            x, 2, "withdrawn", notes="Withdraw assessment for reconsideration."
        ).review.review_version
        == 3
    )
    summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
    assert not summary.review_current and not summary.can_withdraw
    assert [
        row.review_version
        for row in independence.list_reviews(x.parent, x.records.r.db, _authenticated(REVIEWER))
    ] == [3, 2, 1]
    set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
    pairs = x.records.r.db.execute(
        text(
            "SELECT old_values,new_values FROM audit_events WHERE resource_id=:id "
            "AND new_values->>'independence_review_id' IS NOT NULL "
            "ORDER BY (new_values->>'independence_review_version')::int"
        ),
        {"id": x.parent},
    ).all()
    events = [row.new_values for row in pairs]
    assert pairs[0].old_values["independence_review_version"] == 0
    assert pairs[1].old_values["independence_notes_hash"] == events[0]["independence_notes_hash"]
    assert pairs[2].old_values["independence_notes_hash"] == events[1]["independence_notes_hash"]
    assert all("independence_status" not in event for event in events)

    assert len(events) == 3
    assert "notes" not in events[0] and len(events[0]["independence_notes_hash"]) == 64
    assert (
        len(
            independence.list_reviews(
                x.parent, x.records.r.db, _authenticated(REVIEWER), limit=1, offset=1
            )
        )
        == 1
    )


def test_any_plan_edit_stales_review_without_rewriting_prior_decision(plan: Plan) -> None:
    x = plan
    first = record(x)
    parent = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=x.version, objective="Revised objective"),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
    assert summary.audit_version == parent.row_version and not summary.review_current
    assert summary.latest_review and summary.latest_review.id == first.review.id
    with pytest.raises(HTTPException) as stale:
        record(x, 1)
    assert stale.value.status_code == 409
    x.version = parent.row_version
    assert record(x, 1).review.source_audit_version == parent.row_version


def test_creator_and_any_active_team_member_cannot_review(plan: Plan) -> None:
    x = plan
    _grant(x.records.r.db, MANAGER, "audits.review")
    body = independence.ReviewInput(
        expected_audit_version=x.version,
        expected_review_version=0,
        decision="confirmed",
        notes="Cannot self approve",
        independence_attested=True,
    )
    with pytest.raises(HTTPException) as creator:
        independence.create_review(
            x.parent, body, _request(), x.records.r.db, _authenticated(MANAGER)
        )
    assert creator.value.status_code == 409
    person(x.records.r, x.parent, REVIEWER, "auditor")
    x.version = get_audit(x.parent, x.records.r.db, _authenticated(MANAGER)).row_version
    assert not independence.get_independence(
        x.parent, x.records.r.db, _authenticated(REVIEWER)
    ).can_review
    with pytest.raises(HTTPException) as participant:
        record(x)
    assert participant.value.status_code == 409


def test_lead_cannot_review_even_without_team_record(plan: Plan) -> None:
    x = plan
    parent = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=x.version, lead_auditor_user_id=REVIEWER),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    x.version = parent.row_version
    with pytest.raises(HTTPException) as lead:
        record(x)
    assert lead.value.status_code == 409


def test_read_only_and_company_owner_do_not_implicitly_review(plan: Plan) -> None:
    x = plan
    for user in [AUDITOR, OWNER]:
        if user == OWNER:
            with pytest.raises(HTTPException) as owner_read:
                independence.get_independence(x.parent, x.records.r.db, _authenticated(user))
            assert owner_read.value.status_code in {403, 404}
        else:
            summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(user))
            assert not summary.can_review
        with pytest.raises(HTTPException) as denied:
            independence.create_review(
                x.parent,
                independence.ReviewInput(
                    expected_audit_version=x.version,
                    expected_review_version=0,
                    decision="confirmed",
                    notes="No implicit authority",
                    independence_attested=True,
                ),
                _request(),
                x.records.r.db,
                _authenticated(user),
            )
        assert denied.value.status_code in {403, 404}


def test_unknown_cross_unit_and_company_reads_are_hidden(plan: Plan) -> None:
    x = plan
    ids = [uuid4(), x.records.r.audits[UNIT_A_OTHER][0].id, x.records.r.audits[UNIT_B][0].id]
    for target in ids:
        with pytest.raises(HTTPException) as denied:
            independence.get_independence(target, x.records.r.db, _authenticated(REVIEWER))
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as foreign:
        independence.get_independence(x.parent, x.records.r.db, _authenticated(MANAGER, TENANT_B))
    assert foreign.value.status_code == 404


def test_stale_review_version_is_rejected_and_does_not_duplicate_events(plan: Plan) -> None:
    record(plan)
    with pytest.raises(HTTPException) as stale:
        record(plan)
    assert stale.value.status_code == 409
    assert (
        len(independence.list_reviews(plan.parent, plan.records.r.db, _authenticated(REVIEWER)))
        == 1
    )


def test_withdrawal_requires_a_recorded_assessment(plan: Plan) -> None:
    with pytest.raises(HTTPException) as missing:
        record(plan, decision="withdrawn")
    assert missing.value.status_code == 409


def test_closed_planning_rejects_reviews_and_preserves_history(plan: Plan) -> None:
    x = plan
    record(x)
    parent = transition_audit(
        _request(),
        x.parent,
        InternalAuditTransition(
            expected_version=x.version, target_state="cancelled", decision="Replaced plan"
        ),
        x.records.r.db,
        _authenticated(REVIEWER),
    )
    x.version = parent.row_version
    assert not independence.get_independence(
        x.parent, x.records.r.db, _authenticated(REVIEWER)
    ).review_current
    with pytest.raises(HTTPException) as closed:
        record(x, 1)
    assert closed.value.status_code == 409


def test_runtime_cannot_rewrite_delete_or_forge_legacy_confirmation(plan: Plan) -> None:
    x = plan
    row = record(x).review
    for sql in [
        "UPDATE qms_audit_independence_reviews SET notes='rewrite' WHERE id=:id",
        "DELETE FROM qms_audit_independence_reviews WHERE id=:id",
        "TRUNCATE qms_audit_independence_reviews",
    ]:
        set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            x.records.r.db.execute(text(sql), {"id": row.id})
        x.records.r.db.rollback()
    set_request_context(x.records.r.db, user_id=MANAGER, tenant_id=TENANT_A)
    with pytest.raises(DBAPIError):
        x.records.r.db.execute(
            text(
                "UPDATE qms_internal_audits SET independence_status='confirmed', "
                "independence_reviewed_by_user_id=:reviewer, "
                "independence_reviewed_at=CURRENT_TIMESTAMP, row_version=row_version+1, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=:id"
            ),
            {"reviewer": REVIEWER, "id": x.parent},
        )
    x.records.r.db.rollback()
    assert len(independence.list_reviews(x.parent, x.records.r.db, _authenticated(REVIEWER))) == 1


def test_event_failure_rolls_back_new_review(plan: Plan, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Synthetic ledger failure")

    monkeypatch.setattr(audit_service, "record_internal_audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic ledger failure"):
        record(plan)
    assert independence.list_reviews(plan.parent, plan.records.r.db, _authenticated(REVIEWER)) == []


def test_review_requires_explicit_attestation_and_authored_reason() -> None:
    base = {
        "expected_audit_version": 1,
        "expected_review_version": 0,
        "decision": "confirmed",
        "notes": "Reviewed relationships",
        "independence_attested": True,
    }
    cases: list[dict[str, Any]] = [
        {"notes": " "},
        {"independence_attested": False},
        {"independence_attested": "true"},
        {"decision": "withdrawn"},
        {"reviewer_user_id": str(REVIEWER)},
        {"tenant_id": str(TENANT_B)},
    ]
    for changes in cases:
        with pytest.raises(ValidationError):
            independence.ReviewInput.model_validate({**base, **changes})


def test_revoking_review_authority_takes_effect_immediately(plan: Plan) -> None:
    from test_internal_audit_integrity import _actor

    from pmc_api.qms_access import revoke_grant

    x = plan
    set_request_context(x.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    grant = x.records.r.db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE user_id=:user "
            "AND capability='audits.review' AND status='active'"
        ),
        {"user": REVIEWER},
    )
    assert grant
    revoke_grant(x.records.r.db, _actor(OWNER, "owner"), uuid4(), grant)
    assert not independence.get_independence(
        x.parent, x.records.r.db, _authenticated(REVIEWER)
    ).can_review
    with pytest.raises(HTTPException) as revoked:
        record(x)
    assert revoked.value.status_code == 403


def test_inactive_planned_person_blocks_confirmation(plan: Plan) -> None:
    from test_internal_audit_integrity import _engine

    x = plan
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    try:
        with admin.begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status='revoked' "
                    "WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": AUDITOR},
            )
        summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
        assert not summary.can_review and not summary.ready_for_execution
        with pytest.raises(HTTPException) as inactive:
            record(x)
        assert inactive.value.status_code == 409
    finally:
        with admin.begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status='active' "
                    "WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": AUDITOR},
            )
        admin.dispose()


def test_stale_assessment_can_be_withdrawn_after_lead_is_cleared(plan: Plan) -> None:
    x = plan
    record(x)
    parent = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=x.version, lead_auditor_user_id=None),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    x.version = parent.row_version
    summary = independence.get_independence(x.parent, x.records.r.db, _authenticated(REVIEWER))
    assert summary.can_withdraw and not summary.can_review
    withdrawn = record(x, 1, "withdrawn")
    assert withdrawn.review.lead_auditor_user_id is None


def test_runtime_sql_rejects_forged_reviewer_snapshot_plan_or_sequence(plan: Plan) -> None:
    from datetime import UTC, datetime

    from pmc_api.models import QMSAuditIndependenceReview

    x = plan
    cases: list[dict[str, Any]] = [
        {"reviewer_user_id": MANAGER},
        {"reviewer_name_snapshot": "Forged name"},
        {"source_audit_version": x.version - 1},
        {"review_version": 2},
        {"unit_id": UNIT_A_OTHER},
    ]
    for changes in cases:
        set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
        row = QMSAuditIndependenceReview(
            **{
                "id": uuid4(),
                "tenant_id": TENANT_A,
                "unit_id": UNIT_A,
                "audit_id": x.parent,
                "review_version": 1,
                "source_audit_version": x.version,
                "decision": "confirmed",
                "notes": "Runtime SQL invariant check",
                "independence_attested": True,
                "reviewer_user_id": REVIEWER,
                "reviewer_name_snapshot": str(REVIEWER),
                "lead_auditor_user_id": AUDITOR,
                "created_at": datetime.now(UTC),
                **changes,
            }
        )
        x.records.r.db.add(row)
        with pytest.raises(DBAPIError):
            x.records.r.db.flush()
        x.records.r.db.rollback()
    assert independence.list_reviews(x.parent, x.records.r.db, _authenticated(REVIEWER)) == []


def test_concurrent_reviewers_cannot_append_using_the_same_history_version(plan: Plan) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session
    from test_internal_audit_integrity import _engine

    x = plan
    x.records.r.db.rollback()
    gate = Barrier(2, timeout=10)
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")

    def write() -> int:
        with Session(runtime) as db:
            gate.wait()
            try:
                independence.create_review(
                    x.parent,
                    independence.ReviewInput(
                        expected_audit_version=x.version,
                        expected_review_version=0,
                        decision="confirmed",
                        notes="Concurrent independent assessment",
                        independence_attested=True,
                    ),
                    _request(),
                    db,
                    _authenticated(REVIEWER),
                )
                return 201
            except HTTPException as conflict:
                db.rollback()
                return conflict.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(write) for _ in range(2)]
            outcomes = sorted(job.result(timeout=20) for job in jobs)
        assert outcomes == [201, 409]
        assert (
            len(independence.list_reviews(x.parent, x.records.r.db, _authenticated(REVIEWER))) == 1
        )
    finally:
        runtime.dispose()
