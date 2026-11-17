"""Criterion controls exercised against disposable PostgreSQL with forced RLS."""

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

from pmc_api import internal_audit_criteria as criterion
from pmc_api.database import set_request_context
from pmc_api.internal_audits import InternalAuditTransition, get_audit, transition_audit

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


def add(records: PlanningRecords, **changes: Any) -> criterion.CriterionResult:
    identity = inspect(records.audits[UNIT_A][0]).identity
    assert identity is not None
    parent = get_audit(identity[0], records.db, _authenticated(MANAGER))
    return criterion.create_criterion(
        parent.id,
        criterion.CriterionInput(
            expected_audit_version=parent.row_version,
            sequence=10,
            title="Receiving criterion",
            requirement="Verify receiving records have documented acceptance.",
            source_type="internal",
            reference="PROC-RCV v1",
            **changes,
        ),
        _request(),
        records.db,
        _authenticated(MANAGER),
    )


def test_criterion_changes_are_versioned_and_audited_with_the_parent(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    parent = r.audits[UNIT_A][0]
    created = add(r)
    assert created.audit_version == 2 and created.criterion.row_version == 1
    updated = criterion.update_criterion(
        parent.id,
        created.criterion.id,
        criterion.CriterionPatch(
            expected_audit_version=2, expected_version=1, title="Receiving and inspection"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert updated.audit_version == 3 and updated.criterion.row_version == 2
    withdrawn = criterion.withdraw_criterion(
        parent.id,
        created.criterion.id,
        criterion.CriterionWithdrawal(
            expected_audit_version=3, expected_version=2, reason="Superseded boundary"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert withdrawn.audit_version == 4 and withdrawn.criterion.status == "withdrawn"
    assert criterion.list_criteria(parent.id, r.db, _authenticated(MANAGER), status="active") == []
    assert (
        len(criterion.list_criteria(parent.id, r.db, _authenticated(MANAGER), status="withdrawn"))
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
    assert all(e["criterion_id"] == str(created.criterion.id) for e in events)
    assert [e["criterion_status"] for e in events] == ["active", "active", "withdrawn"]
    assert all("Receiving" not in str(e) for e in events)


def test_stale_parent_and_criterion_versions_do_not_mutate_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for parent_version, criterion_version in [(1, 1), (2, 2)]:
        with pytest.raises(HTTPException) as conflict:
            criterion.update_criterion(
                row.criterion.audit_id,
                row.criterion.id,
                criterion.CriterionPatch(
                    expected_audit_version=parent_version,
                    expected_version=criterion_version,
                    title="Lost update",
                ),
                _request(),
                r.db,
                _authenticated(MANAGER),
            )
        assert conflict.value.status_code == 409
        r.db.rollback()
    assert (
        criterion.list_criteria(row.criterion.audit_id, r.db, _authenticated(MANAGER))[0].title
        == "Receiving criterion"
    )


def test_read_only_or_foreign_criterion_authority_cannot_write(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    assert len(criterion.list_criteria(row.criterion.audit_id, r.db, _authenticated(AUDITOR))) == 1
    with pytest.raises(HTTPException) as denied:
        criterion.create_criterion(
            row.criterion.audit_id,
            criterion.CriterionInput(
                expected_audit_version=2,
                sequence=20,
                title="Forbidden",
                requirement="Read only",
                source_type="internal",
                reference="PROC-RCV v1",
            ),
            _request(),
            r.db,
            _authenticated(AUDITOR),
        )
    assert denied.value.status_code == 403
    for actor in [_authenticated(OWNER), _authenticated(MANAGER, TENANT_B)]:
        with pytest.raises(HTTPException) as hidden:
            criterion.list_criteria(row.criterion.audit_id, r.db, actor)
        assert hidden.value.status_code == 404


def test_parent_and_criterion_references_cannot_cross_unit_or_company(
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
            criterion.update_criterion(
                other_id,
                row.criterion.id,
                criterion.CriterionPatch(
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
    parent = get_audit(first.criterion.audit_id, r.db, _authenticated(MANAGER))
    assert parent.row_version == 2
    criterion.withdraw_criterion(
        parent.id,
        first.criterion.id,
        criterion.CriterionWithdrawal(
            expected_audit_version=2, expected_version=1, reason="Replace criterion"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    second = add(r)
    assert second.criterion.id != first.criterion.id and second.audit_version == 4
    assert len(criterion.list_criteria(parent.id, r.db, _authenticated(MANAGER), limit=1)) == 1
    assert (
        len(criterion.list_criteria(parent.id, r.db, _authenticated(MANAGER), limit=1, offset=1))
        == 1
    )


def test_cancelled_parent_and_withdrawn_items_are_immutable(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    criterion.withdraw_criterion(
        row.criterion.audit_id,
        row.criterion.id,
        criterion.CriterionWithdrawal(
            expected_audit_version=2, expected_version=1, reason="Removed from plan"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    with pytest.raises(HTTPException) as immutable:
        criterion.update_criterion(
            row.criterion.audit_id,
            row.criterion.id,
            criterion.CriterionPatch(
                expected_audit_version=3, expected_version=2, requirement="Change history"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert immutable.value.status_code == 409
    _grant(r.db, MANAGER, "audits.review")
    transition_audit(
        _request(),
        row.criterion.audit_id,
        InternalAuditTransition(
            expected_version=3, target_state="cancelled", decision="Duplicate audit"
        ),
        r.db,
        _authenticated(MANAGER),
    )
    assert len(criterion.list_criteria(row.criterion.audit_id, r.db, _authenticated(MANAGER))) == 1
    with pytest.raises(HTTPException) as closed:
        add(r)
    assert closed.value.status_code == 409


def test_direct_sql_cannot_delete_reparent_or_edit_withdrawn_history(
    planning_records: PlanningRecords,
) -> None:
    r = planning_records
    row = add(r)
    for statement in [
        "DELETE FROM qms_audit_criteria WHERE id=:id",
        "TRUNCATE qms_audit_criteria",
        "UPDATE qms_audit_criteria SET audit_id=:other,row_version=row_version+1,"
        "updated_at=clock_timestamp() WHERE id=:id",
    ]:
        set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            r.db.execute(
                text(statement), {"id": row.criterion.id, "other": r.audits[UNIT_A_OTHER][0].id}
            )
            r.db.commit()
        r.db.rollback()
    criterion.withdraw_criterion(
        row.criterion.audit_id,
        row.criterion.id,
        criterion.CriterionWithdrawal(
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
                "UPDATE qms_audit_criteria SET title='Tampered',row_version=row_version+1,"
                "updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": row.criterion.id},
        )
        r.db.commit()
    r.db.rollback()
    set_request_context(r.db, user_id=MANAGER, tenant_id=TENANT_B)
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_criteria")) == 0


def test_revoking_read_hides_parent_and_criterion_rows(planning_records: PlanningRecords) -> None:
    from pmc_api.qms_access import revoke_grant

    r = planning_records
    row = add(r)
    set_request_context(r.db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(r.db, _actor(OWNER, "owner"), uuid4(), r.read_grant_id)
    with pytest.raises(HTTPException) as hidden:
        criterion.list_criteria(row.criterion.audit_id, r.db, _authenticated(MANAGER))
    assert hidden.value.status_code == 404
    assert r.db.scalar(text("SELECT count(*) FROM qms_audit_criteria")) == 0


def test_scope_link_requires_same_audit_unit_company_and_active_status(
    planning_records: PlanningRecords,
) -> None:
    from pmc_api import internal_audit_scope as boundary

    r = planning_records
    target_id = r.audits[UNIT_A][0].id
    for unit, tenant, index in [
        (UNIT_A, TENANT_A, 1),
        (UNIT_A_OTHER, TENANT_A, 0),
        (UNIT_B, TENANT_B, 0),
    ]:
        parent_identity = inspect(r.audits[unit][index]).identity
        assert parent_identity is not None
        parent_id = parent_identity[0]
        result = boundary.create_scope(
            parent_id,
            boundary.ScopeInput(
                expected_audit_version=1, sequence=10, title="Other audit boundary"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER, tenant),
        )
        with pytest.raises(HTTPException) as hidden:
            add(r, scope_id=result.scope.id)
        assert hidden.value.status_code == 404
        r.db.rollback()
    current = get_audit(target_id, r.db, _authenticated(MANAGER))
    item = boundary.create_scope(
        target_id,
        boundary.ScopeInput(
            expected_audit_version=current.row_version, sequence=10, title="Receiving boundary"
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    linked = add(r, scope_id=item.scope.id)
    assert linked.criterion.scope_id == item.scope.id


def test_scope_withdrawal_is_blocked_until_criterion_relinked_or_withdrawn(
    planning_records: PlanningRecords,
) -> None:
    from pmc_api import internal_audit_scope as boundary

    r = planning_records
    parent_id = r.audits[UNIT_A][0].id
    item = boundary.create_scope(
        parent_id,
        boundary.ScopeInput(expected_audit_version=1, sequence=10, title="Receiving boundary"),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    linked = add(r, scope_id=item.scope.id)
    with pytest.raises(HTTPException) as linked_conflict:
        boundary.withdraw_scope(
            parent_id,
            item.scope.id,
            boundary.ScopeWithdrawal(
                expected_audit_version=3, expected_version=1, reason="Should not orphan criterion"
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert linked_conflict.value.status_code == 409
    assert get_audit(parent_id, r.db, _authenticated(MANAGER)).row_version == 3
    # Same guard also applies to direct runtime SQL, not just the API.
    with pytest.raises(DBAPIError):
        r.db.execute(
            text(
                "UPDATE qms_audit_scopes SET status='withdrawn',withdrawal_reason='SQL orphan',"
                "withdrawn_by_user_id=:actor,withdrawn_at=clock_timestamp(),"
                "updated_at=clock_timestamp(),row_version=row_version+1 WHERE id=:id"
            ),
            {"actor": MANAGER, "id": item.scope.id},
        )
        r.db.commit()
    r.db.rollback()
    unlinked = criterion.update_criterion(
        parent_id,
        linked.criterion.id,
        criterion.CriterionPatch(expected_audit_version=3, expected_version=1, scope_id=None),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert unlinked.audit_version == 4 and unlinked.criterion.scope_id is None
    retired = boundary.withdraw_scope(
        parent_id,
        item.scope.id,
        boundary.ScopeWithdrawal(
            expected_audit_version=4,
            expected_version=1,
            reason="Criterion now applies to whole audit",
        ),
        _request(),
        r.db,
        _authenticated(MANAGER),
    )
    assert retired.audit_version == 5
    with pytest.raises(HTTPException) as inactive:
        criterion.update_criterion(
            parent_id,
            linked.criterion.id,
            criterion.CriterionPatch(
                expected_audit_version=5, expected_version=2, scope_id=item.scope.id
            ),
            _request(),
            r.db,
            _authenticated(MANAGER),
        )
    assert inactive.value.status_code == 404


def test_criterion_payload_requires_authored_reference_and_rejects_extra_fields() -> None:
    from pydantic import ValidationError

    cases: list[dict[str, Any]] = [
        {"requirement": " "},
        {"reference": " "},
        {"source_type": "unknown"},
        {"tenant_id": str(TENANT_B)},
        {"sequence": 0},
    ]
    for changes in cases:
        with pytest.raises(ValidationError):
            criterion.CriterionInput.model_validate(
                {
                    "expected_audit_version": 1,
                    "sequence": 10,
                    "title": "Receiving records",
                    "requirement": "Check acceptance record",
                    "reference": "PROC-RCV v1",
                    "source_type": "internal",
                    **changes,
                }
            )
