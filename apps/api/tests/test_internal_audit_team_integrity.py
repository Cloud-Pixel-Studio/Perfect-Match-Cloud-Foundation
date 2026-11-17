"""Team controls exercised against disposable PostgreSQL with forced RLS."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from test_internal_audit_integrity import (
    AUDITOR,
    MANAGER,
    OWNER,
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
from test_internal_audit_integrity import (
    planning_records as planning_records,
)
from test_internal_audit_integrity import (
    seed_identity as seed_identity,
)

from pmc_api import internal_audit_team as team
from pmc_api.database import set_request_context
from pmc_api.internal_audits import InternalAuditTransition, get_audit, transition_audit

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


def add(records: PlanningRecords, **changes: Any) -> team.TeamResult:
    identity = inspect(records.audits[UNIT_A][0]).identity
    assert identity is not None
    parent = get_audit(identity[0], records.db, _authenticated(MANAGER))
    return team.create_team_member(
        parent.id,
        team.TeamInput(
            expected_audit_version=parent.row_version,
            user_id=AUDITOR,
            team_role="auditor",
            responsibilities="Review synthetic receiving records.",
            **changes,
        ),
        _request(),
        records.db,
        _authenticated(MANAGER),
    )


def test_team_changes_are_versioned_and_audited_with_the_parent(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    parent = r.audits[UNIT_A][0]
    created = add(r)
    assert created.audit_version == 2 and created.member.row_version == 1
    updated = team.update_team_member(
        parent.id,
        created.member.id,
        team.TeamPatch(
            expected_audit_version=2,
            expected_version=1,
            responsibilities="Review acceptance records",
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert updated.audit_version == 3 and updated.member.row_version == 2
    withdrawn = team.withdraw_team_member(
        parent.id,
        created.member.id,
        team.TeamWithdrawal(
            expected_audit_version=3, expected_version=2, reason="Superseded boundary"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert withdrawn.audit_version == 4 and withdrawn.member.status == "withdrawn"
    assert team.list_team_members(parent.id, r.db, _authenticated(MANAGER), status="active") == []
    assert (
        len(team.list_team_members(parent.id, r.db, _authenticated(MANAGER), status="withdrawn"))
        == 1
    )
    set_request_context(r.db, user_id=OWNER, tenant_id=TENANT_A)
    events = (
        r.db.execute(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id "
                "AND action='internal_audit.updated' ORDER BY occurred_at,id"
            ),
            {"id": parent.id},
        )
        .scalars()
        .all()
    )
    assert len(events) == 3
    assert all(e["team_member_id"] == str(created.member.id) for e in events)
    assert [e["team_status"] for e in events] == ["active", "active", "withdrawn"]
    assert all("Receiving" not in str(e) for e in events)


def test_stale_parent_and_team_versions_do_not_mutate_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for parent_version, team_version in [(1, 1), (2, 2)]:
        with pytest.raises(HTTPException) as conflict:
            team.update_team_member(
                row.member.audit_id,
                row.member.id,
                team.TeamPatch(
                    expected_audit_version=parent_version,
                    expected_version=team_version,
                    responsibilities="Lost update",
                ),
                _request(),
                r.db,
                _authenticated(MANAGER),
            )
        assert conflict.value.status_code == 409
        r.db.rollback()
    assert (
        team.list_team_members(row.member.audit_id, r.db, _authenticated(MANAGER))[
            0
        ].responsibilities
        == "Review synthetic receiving records."
    )


def test_read_only_or_foreign_team_authority_cannot_write(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    assert len(team.list_team_members(row.member.audit_id, r.db, _authenticated(AUDITOR))) == 1
    with pytest.raises(HTTPException) as denied:
        team.create_team_member(
            row.member.audit_id,
            team.TeamInput(expected_audit_version=2, user_id=OWNER, team_role="auditor"),
            _request(),
            r.db,
            _authenticated(AUDITOR),
        )
    assert denied.value.status_code == 403
    for actor in [_authenticated(OWNER), _authenticated(MANAGER, TENANT_B)]:
        with pytest.raises(HTTPException) as hidden:
            team.list_team_members(row.member.audit_id, r.db, actor)
        assert hidden.value.status_code == 404


def test_parent_and_team_references_cannot_cross_unit_or_company(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    targets = []
    for unit, tenant in [(UNIT_A_OTHER, TENANT_A), (UNIT_B, TENANT_B)]:
        identity = inspect(r.audits[unit][0]).identity
        assert identity is not None
        targets.append((identity[0], tenant))
    for other_id, tenant in targets:
        with pytest.raises(HTTPException) as hidden:
            team.update_team_member(
                other_id,
                row.member.id,
                team.TeamPatch(
                    expected_audit_version=1, expected_version=1, responsibilities="Cross-boundary"
                ),
                _request(),
                r.db,
                _authenticated(MANAGER, tenant),
            )
        assert hidden.value.status_code == 404
        r.db.rollback()


def test_duplicate_active_person_is_atomic_and_reusable_after_withdrawal(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    first = add(r)
    with pytest.raises(HTTPException) as duplicate:
        add(r)
    assert duplicate.value.status_code == 409
    parent = get_audit(first.member.audit_id, r.db, _authenticated(MANAGER))
    assert parent.row_version == 2
    team.withdraw_team_member(
        parent.id,
        first.member.id,
        team.TeamWithdrawal(expected_audit_version=2, expected_version=1, reason="Replace team"),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    second = add(r)
    assert second.member.id != first.member.id and second.audit_version == 4
    assert len(team.list_team_members(parent.id, r.db, _authenticated(MANAGER), limit=1)) == 1
    assert (
        len(team.list_team_members(parent.id, r.db, _authenticated(MANAGER), limit=1, offset=1))
        == 1
    )


def test_cancelled_parent_and_withdrawn_items_are_immutable(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    team.withdraw_team_member(
        row.member.audit_id,
        row.member.id,
        team.TeamWithdrawal(
            expected_audit_version=2, expected_version=1, reason="Removed from plan"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as immutable:
        team.update_team_member(
            row.member.audit_id,
            row.member.id,
            team.TeamPatch(
                expected_audit_version=3, expected_version=2, responsibilities="Change history"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert immutable.value.status_code == 409
    _grant(r.db, MANAGER, "audits.review")
    transition_audit(
        _request(),
        row.member.audit_id,
        InternalAuditTransition(
            expected_version=3, target_state="cancelled", decision="Duplicate audit"
        ),
        r.db,
        _authenticated(MANAGER),
    )
    assert len(team.list_team_members(row.member.audit_id, r.db, _authenticated(MANAGER))) == 1
    with pytest.raises(HTTPException) as closed:
        add(r)
    assert closed.value.status_code == 409


def test_direct_sql_cannot_delete_reparent_or_edit_withdrawn_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for statement in [
        "DELETE FROM qms_audit_team_members WHERE id=:id",
        "TRUNCATE qms_audit_team_members",
        "UPDATE qms_audit_team_members SET audit_id=:other,row_version=row_version+1,"
        "updated_at=clock_timestamp() WHERE id=:id",
    ]:
        set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            r.db.execute(
                text(statement), {"id": row.member.id, "other": r.audits[UNIT_A_OTHER][0].id}
            )
            r.db.commit()
        r.db.rollback()
    team.withdraw_team_member(
        row.member.audit_id,
        row.member.id,
        team.TeamWithdrawal(
            expected_audit_version=2, expected_version=1, reason="Preserve history"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
    with pytest.raises(DBAPIError):
        r.db.execute(
            text(
                "UPDATE qms_audit_team_members SET responsibilities='Tampered',"
                "row_version=row_version+1,"
                "updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": row.member.id},
        )
        r.db.commit()
    r.db.rollback()
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_B)
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_team_members")) == 0


def test_revoking_read_hides_parent_and_team_rows(planning_records: PlanningRecords) -> None:
    from pmc_api.qms_access import revoke_grant

    r = planning_records
    row = add(r)
    set_request_context(r.db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(r.db, _actor(OWNER, "owner"), uuid4(), r.read_grant_id)
    with pytest.raises(HTTPException) as hidden:
        team.list_team_members(row.member.audit_id, r.db, _authenticated(MANAGER))
    assert hidden.value.status_code == 404
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_team_members")) == 0


def test_planned_assignment_does_not_grant_execution_authority(
    planning_records: PlanningRecords,
) -> None:
    from pmc_api.qms_access import require_capability

    r = planning_records
    row = add(r)
    assert row.member.user_id == AUDITOR
    set_request_context(r.db, user_id=AUDITOR, tenant_id=TENANT_A)
    with pytest.raises(HTTPException) as denied:
        require_capability(r.db, "audits.execute", UNIT_A)
    assert denied.value.status_code == 403


def test_lead_cannot_be_an_auditee_in_either_write_direction(
    planning_records: PlanningRecords,
) -> None:
    from pmc_api.internal_audits import InternalAuditPatch, update_audit

    r = planning_records
    parent_id = r.audits[UNIT_A][0].id
    row = add(r)
    update_audit(
        _request(),
        parent_id,
        InternalAuditPatch(expected_version=2, lead_auditor_user_id=AUDITOR),
        r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as conflict:
        team.update_team_member(
            parent_id,
            row.member.id,
            team.TeamPatch(expected_audit_version=3, expected_version=1, team_role="auditee"),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert conflict.value.status_code == 409
    update_audit(
        _request(),
        parent_id,
        InternalAuditPatch(expected_version=3, lead_auditor_user_id=None),
        r.db,
        _authenticated(MANAGER),
    )
    team.update_team_member(
        parent_id,
        row.member.id,
        team.TeamPatch(expected_audit_version=4, expected_version=1, team_role="auditee"),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as leader_conflict:
        update_audit(
            _request(),
            parent_id,
            InternalAuditPatch(expected_version=5, lead_auditor_user_id=AUDITOR),
            r.db,
            _authenticated(MANAGER),
        )
    assert leader_conflict.value.status_code == 409
    assert get_audit(parent_id, r.db, _authenticated(MANAGER)).lead_auditor_user_id is None


def test_identity_snapshot_is_immutable_and_inactive_person_can_be_retired(
    planning_records: PlanningRecords,
) -> None:
    from test_internal_audit_integrity import _engine

    r = planning_records
    row = add(r)
    parent_id, member_id, snapshot = (
        row.member.audit_id,
        row.member.id,
        row.member.display_name_snapshot,
    )
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
    with pytest.raises(DBAPIError):
        r.db.execute(
            text(
                "UPDATE qms_audit_team_members SET display_name_snapshot='Forged',"
                "row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": member_id},
        )
        r.db.commit()
    r.db.rollback()
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='revoked' "
                "WHERE tenant_id=:tenant AND user_id=:person"
            ),
            {"tenant": TENANT_A, "person": AUDITOR},
        )
    try:
        withdrawn = team.withdraw_team_member(
            parent_id,
            member_id,
            team.TeamWithdrawal(
                expected_audit_version=2, expected_version=1, reason="Person no longer participates"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
        assert (
            withdrawn.member.display_name_snapshot == snapshot
            and withdrawn.member.status == "withdrawn"
        )
    finally:
        with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status='active' "
                    "WHERE tenant_id=:tenant AND user_id=:person"
                ),
                {"tenant": TENANT_A, "person": AUDITOR},
            )


def test_missing_person_and_forged_identity_fields_are_rejected(
    planning_records: PlanningRecords,
) -> None:
    from pydantic import ValidationError

    r = planning_records
    parent_id = r.audits[UNIT_A][0].id
    with pytest.raises(HTTPException) as missing:
        team.create_team_member(
            parent_id,
            team.TeamInput(expected_audit_version=1, user_id=uuid4(), team_role="auditor"),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert missing.value.status_code == 404
    with pytest.raises(ValidationError):
        team.TeamInput.model_validate(
            {
                "expected_audit_version": 1,
                "user_id": str(AUDITOR),
                "team_role": "auditor",
                "display_name_snapshot": "Forged",
            }
        )
    with pytest.raises(ValidationError):
        team.TeamPatch.model_validate(
            {"expected_audit_version": 1, "expected_version": 1, "user_id": str(OWNER)}
        )
