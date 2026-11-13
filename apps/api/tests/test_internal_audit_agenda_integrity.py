"""Agenda constraints exercised against disposable PostgreSQL and real services."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
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
    PlanningRecords,
    _actor,
    _authenticated,
    _grant,
    _request,
)
from test_internal_audit_integrity import planning_records as planning_records
from test_internal_audit_integrity import seed_identity as seed_identity

from pmc_api import internal_audit_agenda as agenda
from pmc_api import internal_audit_scope as scope
from pmc_api import internal_audit_team as team
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
class Records:
    r: PlanningRecords
    parent: UUID
    auditor: UUID
    auditee: UUID
    scope: UUID


def person(
    r: PlanningRecords, parent: UUID, user: UUID, role: str, tenant: UUID = TENANT_A
) -> UUID:
    current = get_audit(parent, r.db, _authenticated(MANAGER, tenant))
    result = team.create_team_member(
        parent,
        team.TeamInput.model_validate(
            {"expected_audit_version": current.row_version, "user_id": user, "team_role": role}
        ),
        _request(),
        r.db,
        _authenticated(MANAGER, tenant),
    )
    return result.member.id


@pytest.fixture
def records(planning_records: PlanningRecords) -> Records:
    r = planning_records
    parent = r.audits[UNIT_A][0].id
    auditor = person(r, parent, AUDITOR, "auditor")
    auditee = person(r, parent, OWNER, "auditee")
    boundary = scope.create_scope(
        parent,
        scope.ScopeInput(expected_audit_version=3, sequence=10, title="Receiving boundary"),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    return Records(r, parent, auditor, auditee, boundary.scope.id)


def add(x: Records, **changes: Any) -> agenda.AgendaResult:
    current = get_audit(x.parent, x.r.db, _authenticated(MANAGER))
    body = {
        "expected_audit_version": current.row_version,
        "sequence": 10,
        "title": "Receiving review",
        "objective": "Evaluate acceptance records",
        "method": "sampling",
        "location": "Receiving bay",
        "starts_at": "2027-04-01T09:00:00Z",
        "ends_at": "2027-04-01T10:00:00Z",
        "scope_id": x.scope,
        "auditor_team_member_id": x.auditor,
        "auditee_team_member_id": x.auditee,
        **changes,
    }
    return agenda.create_agenda_item(
        x.parent,
        agenda.AgendaInput.model_validate(body),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )


def test_agenda_lifecycle_names_parent_versions_and_hashed_events(records: Records) -> None:
    x = records
    row = add(x)
    assert (
        row.audit_version == 5
        and row.item.row_version == 1
        and row.item.auditor_name == str(AUDITOR)
    )
    edited = agenda.update_agenda_item(
        x.parent,
        row.item.id,
        agenda.AgendaPatch(
            expected_audit_version=5, expected_version=1, title="Revised receiving review"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    assert edited.audit_version == 6 and edited.item.row_version == 2
    retired = agenda.withdraw_agenda_item(
        x.parent,
        row.item.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=6, expected_version=2, reason="Replanned activity"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    assert retired.audit_version == 7 and retired.item.status == "withdrawn"
    assert agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER), status="active") == []
    set_request_context(x.r.db, user_id=OWNER, tenant_id=TENANT_A)
    events = (
        x.r.db.execute(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id "
                "AND new_values->>'agenda_id' IS NOT NULL ORDER BY occurred_at,id"
            ),
            {"id": x.parent},
        )
        .scalars()
        .all()
    )
    assert len(events) == 3 and [e["agenda_status"] for e in events] == [
        "active",
        "active",
        "withdrawn",
    ]
    assert all(e["agenda_id"] == str(row.item.id) and "Receiving" not in str(e) for e in events)


def test_stale_parent_or_item_never_repeats_mutation(records: Records) -> None:
    x = records
    row = add(x)
    for parent, item in [(4, 1), (5, 2)]:
        with pytest.raises(HTTPException) as conflict:
            agenda.update_agenda_item(
                x.parent,
                row.item.id,
                agenda.AgendaPatch(
                    expected_audit_version=parent, expected_version=item, title="Lost update"
                ),
                _request(),
                x.r.db,
                _authenticated(MANAGER),
            )
        assert conflict.value.status_code == 409
        x.r.db.rollback()
    assert get_audit(x.parent, x.r.db, _authenticated(MANAGER)).row_version == 5
    assert (
        agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER))[0].title == "Receiving review"
    )


def test_read_only_missing_and_foreign_authority(records: Records) -> None:
    x = records
    row = add(x)
    assert len(agenda.list_agenda(x.parent, x.r.db, _authenticated(AUDITOR))) == 1
    with pytest.raises(HTTPException) as denied:
        agenda.withdraw_agenda_item(
            x.parent,
            row.item.id,
            agenda.AgendaWithdrawal(
                expected_audit_version=5, expected_version=1, reason="Forbidden"
            ),
            _request(),
            x.r.db,
            _authenticated(AUDITOR),
        )
    assert denied.value.status_code == 403
    for auth in [_authenticated(OWNER), _authenticated(MANAGER, TENANT_B)]:
        with pytest.raises(HTTPException) as hidden:
            agenda.list_agenda(x.parent, x.r.db, auth)
        assert hidden.value.status_code == 404


def test_item_cannot_be_reused_under_other_parent_unit_company(records: Records) -> None:
    x = records
    row = add(x)
    targets = [
        (inspect(x.r.audits[u][0]).identity, t)
        for u, t in [(UNIT_A_OTHER, TENANT_A), (UNIT_B, TENANT_B)]
    ]
    for identity, tenant in targets:
        assert identity is not None
        with pytest.raises(HTTPException) as hidden:
            agenda.update_agenda_item(
                identity[0],
                row.item.id,
                agenda.AgendaPatch(
                    expected_audit_version=1, expected_version=1, title="Wrong audit"
                ),
                _request(),
                x.r.db,
                _authenticated(MANAGER, tenant),
            )
        assert hidden.value.status_code == 404
        x.r.db.rollback()


def test_duplicate_order_atomic_and_reusable_history(records: Records) -> None:
    x = records
    row = add(x)
    with pytest.raises(HTTPException) as duplicate:
        add(x, starts_at="2027-04-01T11:00:00Z", ends_at="2027-04-01T12:00:00Z")
    assert duplicate.value.status_code == 409
    assert get_audit(x.parent, x.r.db, _authenticated(MANAGER)).row_version == 5
    agenda.withdraw_agenda_item(
        x.parent,
        row.item.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=5, expected_version=1, reason="Replace activity"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    replacement = add(x)
    assert replacement.item.id != row.item.id and replacement.audit_version == 7
    assert (
        len(agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER), limit=1, offset=1)) == 1
    )


def test_participant_overlaps_rejected_but_adjacent_and_parallel_allowed(records: Records) -> None:
    x = records
    add(x)
    with pytest.raises(HTTPException) as overlap:
        add(x, sequence=20, starts_at="2027-04-01T09:30:00Z", ends_at="2027-04-01T10:30:00Z")
    assert overlap.value.status_code == 409
    adjacent = add(x, sequence=20, starts_at="2027-04-01T10:00:00Z", ends_at="2027-04-01T11:00:00Z")
    assert adjacent.audit_version == 6
    other_auditor = person(x.r, x.parent, MANAGER, "auditor")
    with pytest.raises(HTTPException) as same_auditee:
        add(
            x,
            sequence=30,
            auditor_team_member_id=other_auditor,
            starts_at="2027-04-01T09:30:00Z",
            ends_at="2027-04-01T10:30:00Z",
        )
    assert same_auditee.value.status_code == 409
    other_auditee = person(x.r, x.parent, REVIEWER, "auditee")
    parallel = add(
        x,
        sequence=30,
        auditor_team_member_id=other_auditor,
        auditee_team_member_id=other_auditee,
        starts_at="2027-04-01T09:30:00Z",
        ends_at="2027-04-01T10:30:00Z",
    )
    assert parallel.item.auditor_team_member_id == other_auditor


def test_agenda_must_fit_parent_utc_window(records: Records) -> None:
    x = records
    for changes in [{"starts_at": "2027-03-31T23:00:00Z"}, {"ends_at": "2028-01-01T01:00:00Z"}]:
        with pytest.raises(HTTPException) as outside:
            add(x, **changes)
        assert outside.value.status_code == 409
    assert get_audit(x.parent, x.r.db, _authenticated(MANAGER)).row_version == 4


def test_exact_active_scope_and_role_links_required(records: Records) -> None:
    x = records
    for changes in [
        {"scope_id": uuid4()},
        {"auditor_team_member_id": x.auditee},
        {"auditee_team_member_id": x.auditor},
    ]:
        with pytest.raises(HTTPException) as invalid:
            add(x, **changes)
        assert invalid.value.status_code == 404
        x.r.db.rollback()
    for unit, tenant, index in [
        (UNIT_A, TENANT_A, 1),
        (UNIT_A_OTHER, TENANT_A, 0),
        (UNIT_B, TENANT_B, 0),
    ]:
        identity = inspect(x.r.audits[unit][index]).identity
        assert identity is not None
        current = get_audit(identity[0], x.r.db, _authenticated(MANAGER, tenant))
        foreign = scope.create_scope(
            identity[0],
            scope.ScopeInput(
                expected_audit_version=current.row_version, sequence=10, title="Other boundary"
            ),
            _request(),
            x.r.db,
            _authenticated(MANAGER, tenant),
        )
        with pytest.raises(HTTPException) as hidden:
            add(x, scope_id=foreign.scope.id)
        assert hidden.value.status_code == 404
        x.r.db.rollback()


def test_active_agenda_protects_scope_and_team_then_history_stays_readable(
    records: Records,
) -> None:
    x = records
    row = add(x)
    operations: list[Callable[[], object]] = [
        lambda: scope.withdraw_scope(
            x.parent,
            x.scope,
            scope.ScopeWithdrawal(
                expected_audit_version=5, expected_version=1, reason="Orphan scope"
            ),
            _request(),
            x.r.db,
            _authenticated(MANAGER),
        ),
        lambda: team.withdraw_team_member(
            x.parent,
            x.auditor,
            team.TeamWithdrawal(
                expected_audit_version=5, expected_version=1, reason="Orphan auditor"
            ),
            _request(),
            x.r.db,
            _authenticated(MANAGER),
        ),
        lambda: team.update_team_member(
            x.parent,
            x.auditor,
            team.TeamPatch(expected_audit_version=5, expected_version=1, team_role="auditee"),
            _request(),
            x.r.db,
            _authenticated(MANAGER),
        ),
    ]
    for operation in operations:
        with pytest.raises(HTTPException) as conflict:
            operation()
        assert conflict.value.status_code == 409
        x.r.db.rollback()
    agenda.withdraw_agenda_item(
        x.parent,
        row.item.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=5, expected_version=1, reason="Replan first"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    scope.withdraw_scope(
        x.parent,
        x.scope,
        scope.ScopeWithdrawal(
            expected_audit_version=6, expected_version=1, reason="Retire boundary"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    team.withdraw_team_member(
        x.parent,
        x.auditor,
        team.TeamWithdrawal(
            expected_audit_version=7, expected_version=1, reason="Retire assignment"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    history = agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER), status="withdrawn")
    assert history[0].auditor_name == str(AUDITOR)


def test_parent_dates_cannot_strand_active_agenda(records: Records) -> None:
    x = records
    add(x)
    with pytest.raises(HTTPException) as conflict:
        update_audit(
            _request(),
            x.parent,
            InternalAuditPatch(expected_version=5, planned_start=date(2027, 4, 2)),
            x.r.db,
            _authenticated(MANAGER),
        )
    assert conflict.value.status_code == 409
    assert get_audit(x.parent, x.r.db, _authenticated(MANAGER)).row_version == 5
    updated = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=5, planned_end=date(2027, 4, 2)),
        x.r.db,
        _authenticated(MANAGER),
    )
    assert updated.row_version == 6
    item = agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER))[0]
    agenda.withdraw_agenda_item(
        x.parent,
        item.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=6, expected_version=1, reason="Move audit to next day"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    replanned = update_audit(
        _request(),
        x.parent,
        InternalAuditPatch(expected_version=7, planned_start=date(2027, 4, 2)),
        x.r.db,
        _authenticated(MANAGER),
    )
    assert replanned.row_version == 8
    historical = agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER), status="withdrawn")
    assert historical[0].starts_at.date() == date(2027, 4, 1)


def test_sql_delete_reparent_invalid_times_and_retired_content_rejected(records: Records) -> None:
    x = records
    row = add(x)
    other_identity = inspect(x.r.audits[UNIT_A][1]).identity
    assert other_identity is not None
    for statement in [
        "DELETE FROM qms_audit_agenda_items WHERE id=:id",
        "TRUNCATE qms_audit_agenda_items",
        (
            "UPDATE qms_audit_agenda_items SET ends_at=starts_at,"
            "row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
        ),
        (
            "UPDATE qms_audit_agenda_items SET audit_id=:other,"
            "row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
        ),
    ]:
        set_request_context(x.r.db, user_id=MANAGER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            x.r.db.execute(
                text(statement),
                {"id": row.item.id, "other": other_identity[0]},
            )
            x.r.db.commit()
        x.r.db.rollback()
    agenda.withdraw_agenda_item(
        x.parent,
        row.item.id,
        agenda.AgendaWithdrawal(
            expected_audit_version=5, expected_version=1, reason="Keep history"
        ),
        _request(),
        x.r.db,
        _authenticated(MANAGER),
    )
    set_request_context(x.r.db, user_id=MANAGER, tenant_id=TENANT_A)
    with pytest.raises(DBAPIError):
        x.r.db.execute(
            text(
                "UPDATE qms_audit_agenda_items SET title='Tampered',"
                "row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": row.item.id},
        )
        x.r.db.commit()
    x.r.db.rollback()


def test_cancelled_audit_and_revoked_read_remain_enforced(records: Records) -> None:
    from pmc_api.qms_access import revoke_grant

    x = records
    row = add(x)
    _grant(x.r.db, MANAGER, "audits.review")
    transition_audit(
        _request(),
        x.parent,
        InternalAuditTransition(
            expected_version=5, target_state="cancelled", decision="Cancel plan"
        ),
        x.r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as closed:
        add(x, sequence=20)
    assert closed.value.status_code == 409
    set_request_context(x.r.db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(x.r.db, _actor(OWNER, "owner"), uuid4(), x.r.read_grant_id)
    with pytest.raises(HTTPException) as hidden:
        agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER))
    assert hidden.value.status_code == 404
    assert x.r.db.scalar(text("SELECT count(*) FROM qms_audit_agenda_items")) == 0
    assert row.item.row_version == 1


def test_team_role_filter_returns_exact_choices(records: Records) -> None:
    x = records
    assert [
        r.id
        for r in team.list_team_members(
            x.parent, x.r.db, _authenticated(MANAGER), status="active", team_role="auditor"
        )
    ] == [x.auditor]
    assert [
        r.id
        for r in team.list_team_members(
            x.parent, x.r.db, _authenticated(MANAGER), status="active", team_role="auditee"
        )
    ] == [x.auditee]


def test_timestamp_contract_rejects_naive_seconds_and_nonpositive_intervals() -> None:
    base = {
        "expected_audit_version": 1,
        "sequence": 10,
        "title": "Planning",
        "method": "meeting",
        "auditor_team_member_id": str(uuid4()),
        "starts_at": "2027-04-01T09:00:00Z",
        "ends_at": "2027-04-01T10:00:00Z",
    }
    cases: list[dict[str, Any]] = [
        {"starts_at": "2027-04-01T09:00:00"},
        {"starts_at": "2027-04-01T09:00:01Z"},
        {"ends_at": "2027-04-01T09:00:00Z"},
        {"tenant_id": str(TENANT_B)},
    ]
    for changes in cases:
        with pytest.raises(ValidationError):
            agenda.AgendaInput.model_validate({**base, **changes})


def test_concurrent_runtime_sql_cannot_double_book_an_auditor(records: Records) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session
    from test_internal_audit_integrity import _engine

    from pmc_api.models import QMSAuditAgendaItem

    x = records
    gate = Barrier(2, timeout=10)
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")

    def write(order: int) -> str:
        with Session(runtime) as db:
            set_request_context(db, user_id=MANAGER, tenant_id=TENANT_A)
            now = datetime.now(UTC)
            item = QMSAuditAgendaItem(
                id=uuid4(),
                tenant_id=TENANT_A,
                unit_id=UNIT_A,
                audit_id=x.parent,
                sequence=order,
                title="Concurrent activity",
                objective="",
                method="sampling",
                location="",
                starts_at=datetime(2027, 4, 1, 9, tzinfo=UTC),
                ends_at=datetime(2027, 4, 1, 10, tzinfo=UTC),
                scope_id=x.scope,
                auditor_team_member_id=x.auditor,
                auditee_team_member_id=None,
                status="active",
                row_version=1,
                withdrawal_reason="",
                withdrawn_by_user_id=None,
                withdrawn_at=None,
                created_by_user_id=MANAGER,
                created_at=now,
                updated_at=now,
            )
            gate.wait()
            try:
                db.add(item)
                db.commit()
                return "committed"
            except DBAPIError as error:
                db.rollback()
                detail = error.orig.args[0] if error.orig and error.orig.args else {}
                return str(detail.get("C")) if isinstance(detail, dict) else "unexpected error"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(write, order) for order in [10, 20]]
            outcomes = sorted(job.result(timeout=20) for job in jobs)
        assert outcomes == ["23514", "committed"]
        # The concurrent writers use separate sessions; discard the fixture identity cache.
        x.r.db.expire_all()
        assert len(agenda.list_agenda(x.parent, x.r.db, _authenticated(MANAGER))) == 1
        assert get_audit(x.parent, x.r.db, _authenticated(MANAGER)).row_version == 5
    finally:
        runtime.dispose()
