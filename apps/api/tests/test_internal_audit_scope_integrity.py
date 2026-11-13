"""Scope controls exercised against disposable PostgreSQL with forced RLS."""

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

from pmc_api import internal_audit_scope as scope
from pmc_api.database import set_request_context
from pmc_api.internal_audits import InternalAuditTransition, get_audit, transition_audit
from pmc_api.processes import ProcessInput, create_process

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


def add(records: PlanningRecords, **changes: Any) -> scope.ScopeResult:
    parent = get_audit(records.audits[UNIT_A][0].id, records.db, _authenticated(MANAGER))
    return scope.create_scope(
        parent.id,
        scope.ScopeInput(
            expected_audit_version=parent.row_version,
            sequence=10,
            title="Receiving scope",
            description="Synthetic audit boundary",
            **changes,
        ),
        _request(),
        records.db,
        _authenticated(MANAGER),
    )


def test_scope_changes_are_versioned_and_audited_with_the_parent(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    parent = r.audits[UNIT_A][0]
    created = add(r)
    assert created.audit_version == 2 and created.scope.row_version == 1
    updated = scope.update_scope(
        parent.id,
        created.scope.id,
        scope.ScopePatch(
            expected_audit_version=2, expected_version=1, title="Receiving and inspection"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert updated.audit_version == 3 and updated.scope.row_version == 2
    withdrawn = scope.withdraw_scope(
        parent.id,
        created.scope.id,
        scope.ScopeWithdrawal(
            expected_audit_version=3, expected_version=2, reason="Superseded boundary"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert withdrawn.audit_version == 4 and withdrawn.scope.status == "withdrawn"
    assert scope.list_scopes(parent.id, r.db, _authenticated(MANAGER), status="active") == []
    assert len(scope.list_scopes(parent.id, r.db, _authenticated(MANAGER), status="withdrawn")) == 1
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
    assert all(e["scope_id"] == str(created.scope.id) for e in events)
    assert [e["scope_status"] for e in events] == ["active", "active", "withdrawn"]
    assert all("Receiving" not in str(e) for e in events)


def test_stale_parent_and_scope_versions_do_not_mutate_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for parent_version, scope_version in [(1, 1), (2, 2)]:
        with pytest.raises(HTTPException) as conflict:
            scope.update_scope(
                row.scope.audit_id,
                row.scope.id,
                scope.ScopePatch(
                    expected_audit_version=parent_version,
                    expected_version=scope_version,
                    title="Lost update",
                ),
                _request(),
                r.db,
                _authenticated(MANAGER),
            )
        assert conflict.value.status_code == 409
        r.db.rollback()
    assert (
        scope.list_scopes(row.scope.audit_id, r.db, _authenticated(MANAGER))[0].title
        == "Receiving scope"
    )


def test_read_only_or_foreign_scope_authority_cannot_write(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    assert len(scope.list_scopes(row.scope.audit_id, r.db, _authenticated(AUDITOR))) == 1
    with pytest.raises(HTTPException) as denied:
        scope.create_scope(
            row.scope.audit_id,
            scope.ScopeInput(expected_audit_version=2, sequence=20, title="Forbidden"),
            _request(),
            r.db,
            _authenticated(AUDITOR),
        )
    assert denied.value.status_code == 403
    for actor in [_authenticated(OWNER), _authenticated(MANAGER, TENANT_B)]:
        with pytest.raises(HTTPException) as hidden:
            scope.list_scopes(row.scope.audit_id, r.db, actor)
        assert hidden.value.status_code == 404


def test_parent_and_scope_references_cannot_cross_unit_or_company(
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
            scope.update_scope(
                other_id,
                row.scope.id,
                scope.ScopePatch(
                    expected_audit_version=1, expected_version=1, title="Cross-boundary"
                ),
                _request(),
                r.db,
                _authenticated(MANAGER, tenant),
            )
        assert hidden.value.status_code == 404
        r.db.rollback()


def test_duplicate_active_sequence_is_atomic_and_reusable_after_withdrawal(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    first = add(r)
    with pytest.raises(HTTPException) as duplicate:
        add(r)
    assert duplicate.value.status_code == 409
    parent = get_audit(first.scope.audit_id, r.db, _authenticated(MANAGER))
    assert parent.row_version == 2
    scope.withdraw_scope(
        parent.id,
        first.scope.id,
        scope.ScopeWithdrawal(expected_audit_version=2, expected_version=1, reason="Replace scope"),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    second = add(r)
    assert second.scope.id != first.scope.id and second.audit_version == 4
    assert len(scope.list_scopes(parent.id, r.db, _authenticated(MANAGER), limit=1)) == 1
    assert len(scope.list_scopes(parent.id, r.db, _authenticated(MANAGER), limit=1, offset=1)) == 1


def test_cancelled_parent_and_withdrawn_items_are_immutable(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    scope.withdraw_scope(
        row.scope.audit_id,
        row.scope.id,
        scope.ScopeWithdrawal(
            expected_audit_version=2, expected_version=1, reason="Removed from plan"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as immutable:
        scope.update_scope(
            row.scope.audit_id,
            row.scope.id,
            scope.ScopePatch(
                expected_audit_version=3, expected_version=2, description="Change history"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert immutable.value.status_code == 409
    _grant(r.db, MANAGER, "audits.review")
    transition_audit(
        _request(),
        row.scope.audit_id,
        InternalAuditTransition(
            expected_version=3, target_state="cancelled", decision="Duplicate audit"
        ),
        r.db,
        _authenticated(MANAGER),
    )
    assert len(scope.list_scopes(row.scope.audit_id, r.db, _authenticated(MANAGER))) == 1
    with pytest.raises(HTTPException) as closed:
        add(r)
    assert closed.value.status_code == 409


def test_process_link_requires_read_access_and_exact_active_scope(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    with pytest.raises(HTTPException) as denied:
        add(r, process_id=uuid4())
    assert denied.value.status_code == 403
    _grant(r.db, MANAGER, "processes.read")
    with pytest.raises(HTTPException) as missing:
        add(r, process_id=uuid4())
    assert missing.value.status_code == 404
    _grant(r.db, MANAGER, "processes.manage")
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
    process = create_process(
        r.db,
        _actor(MANAGER, "member"),
        uuid4(),
        ProcessInput(unit_id=UNIT_A, code="SCOPE-P-" + uuid4().hex[:8], name="Controlled process"),
    )
    row = add(r, process_id=process.id)
    assert row.scope.process_id == process.id


def test_direct_sql_cannot_delete_reparent_or_edit_withdrawn_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for statement in [
        "DELETE FROM qms_audit_scopes WHERE id=:id",
        "TRUNCATE qms_audit_scopes",
        "UPDATE qms_audit_scopes SET audit_id=:other,row_version=row_version+1,"
        "updated_at=clock_timestamp() WHERE id=:id",
    ]:
        set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            r.db.execute(
                text(statement), {"id": row.scope.id, "other": r.audits[UNIT_A_OTHER][0].id}
            )
            r.db.commit()
        r.db.rollback()
    scope.withdraw_scope(
        row.scope.audit_id,
        row.scope.id,
        scope.ScopeWithdrawal(
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
                "UPDATE qms_audit_scopes SET title='Tampered',row_version=row_version+1,"
                "updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": row.scope.id},
        )
        r.db.commit()
    r.db.rollback()
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_B)
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_scopes")) == 0


def test_revoking_read_hides_parent_and_scope_rows(planning_records: PlanningRecords) -> None:
    from pmc_api.qms_access import revoke_grant

    r = planning_records
    row = add(r)
    set_request_context(r.db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(r.db, _actor(OWNER, "owner"), uuid4(), r.read_grant_id)
    with pytest.raises(HTTPException) as hidden:
        scope.list_scopes(row.scope.audit_id, r.db, _authenticated(MANAGER))
    assert hidden.value.status_code == 404
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_scopes")) == 0
