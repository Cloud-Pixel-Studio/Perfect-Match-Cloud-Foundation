# ruff: noqa: E501 -- controlled SQL assertions in disposable PostgreSQL.
"""Purpose-bound aggregate access checks, without widening grant visibility."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_internal_audit_agenda_integrity import person
from test_internal_audit_agenda_integrity import records as records
from test_internal_audit_independence_integrity import Plan, record
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

from pmc_api import internal_audit_independence as independence
from pmc_api import internal_audit_team as team
from pmc_api.database import set_request_context
from pmc_api.internal_audits import get_audit
from pmc_api.qms_access import require_capability, revoke_grant

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required"
    ),
]


def summary(x: Plan, user: Any = REVIEWER) -> independence.IndependenceSummary:
    return independence.get_independence(x.parent, x.records.r.db, _authenticated(user))


def test_only_explicit_read_and_execute_grants_satisfy_access_not_assignment(plan: Plan) -> None:
    x = plan
    before = summary(x)
    assert before.execution_authority.status == "blocked"
    assert (
        before.execution_authority.planned_auditors,
        before.execution_authority.authorized_auditors,
    ) == (1, 0)
    _grant(x.records.r.db, AUDITOR, "audits.execute")
    after = summary(x)
    assert (
        after.execution_authority.status == "passed"
        and after.execution_authority.authorized_auditors == 1
    )
    assert not after.ready_for_execution
    assert {c.code: c.status for c in after.checks}["competence"] == "unverified"
    set_request_context(x.records.r.db, user_id=AUDITOR, tenant_id=TENANT_A)
    require_capability(x.records.r.db, "audits.execute", UNIT_A)


def test_revocation_is_immediate_without_invalidating_the_independence_history(plan: Plan) -> None:
    x = plan
    grant = _grant(x.records.r.db, AUDITOR, "audits.execute")
    decision = record(x).review.id
    assert summary(x).execution_authority.status == "passed"
    set_request_context(x.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(x.records.r.db, _actor(OWNER, "owner"), uuid4(), grant.id)
    after = summary(x)
    assert after.execution_authority.status == "blocked" and after.review_current
    assert after.latest_review and after.latest_review.id == decision
    assert after.audit_version == x.version and not after.ready_for_execution


def test_read_only_users_receive_no_team_access_counts(plan: Plan) -> None:
    after = summary(plan, AUDITOR)
    assert after.execution_authority.status == "unverified"
    assert after.execution_authority.planned_auditors is None
    assert after.execution_authority.authorized_auditors is None
    assert not after.ready_for_execution


def test_sql_rejects_unscoped_foreign_unknown_and_unauthorized_calls_uniformly(plan: Plan) -> None:
    x = plan
    identities = [
        uuid4(),
        x.records.r.audits[UNIT_A_OTHER][0].id,
        x.records.r.audits[UNIT_B][0].id,
        None,
    ]
    cases = [(REVIEWER, TENANT_A, parent) for parent in identities]
    cases.extend(
        [
            (AUDITOR, TENANT_A, x.parent),
            (MANAGER, TENANT_A, x.parent),
            (MANAGER, TENANT_B, x.parent),
        ]
    )
    for user, tenant, parent in cases:
        set_request_context(x.records.r.db, user_id=user, tenant_id=tenant)
        with pytest.raises(DBAPIError) as denied:
            x.records.r.db.execute(
                text("SELECT * FROM public.qms_audit_execution_authority(:id)"), {"id": parent}
            )
        assert denied.value.orig is not None
        detail = denied.value.orig.args[0]
        assert (
            detail["C"] == "42501"
            and detail["M"] == "audit execution-access verification unavailable"
        )
        x.records.r.db.rollback()
    with pytest.raises(DBAPIError) as unscoped:
        x.records.r.db.execute(
            text("SELECT * FROM public.qms_audit_execution_authority(:id)"), {"id": x.parent}
        )
    assert unscoped.value.orig is not None
    assert unscoped.value.orig.args[0]["C"] == "42501"
    x.records.r.db.rollback()


def test_every_active_auditor_is_checked_and_withdrawn_assignments_are_excluded(plan: Plan) -> None:
    x = plan
    _grant(x.records.r.db, AUDITOR, "audits.execute")
    second = person(x.records.r, x.parent, MANAGER, "auditor")
    after = summary(x)
    assert (
        after.execution_authority.planned_auditors,
        after.execution_authority.authorized_auditors,
    ) == (2, 1)
    _grant(x.records.r.db, MANAGER, "audits.execute")
    assert summary(x).execution_authority.status == "passed"
    parent = get_audit(x.parent, x.records.r.db, _authenticated(MANAGER))
    team.withdraw_team_member(
        x.parent,
        second,
        team.TeamWithdrawal(
            expected_audit_version=parent.row_version,
            expected_version=1,
            reason="Change planned team",
        ),
        _request(),
        x.records.r.db,
        _authenticated(MANAGER),
    )
    after = summary(x)
    assert (
        after.execution_authority.planned_auditors,
        after.execution_authority.authorized_auditors,
    ) == (1, 1)


@pytest.mark.parametrize("entity", ["membership", "user"])
def test_revoked_membership_or_disabled_user_blocks_target_access(plan: Plan, entity: str) -> None:
    x = plan
    _grant(x.records.r.db, AUDITOR, "audits.execute")
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    update = (
        "UPDATE memberships SET status=:status WHERE tenant_id=:tenant AND user_id=:person"
        if entity == "membership"
        else "UPDATE users SET status=:status WHERE id=:person"
    )
    try:
        with admin.begin() as connection:
            connection.execute(
                text(update),
                {
                    "tenant": TENANT_A,
                    "person": AUDITOR,
                    "status": "revoked" if entity == "membership" else "disabled",
                },
            )
        after = summary(x)
        assert (
            after.execution_authority.authorized_auditors == 0
            and after.execution_authority.status == "blocked"
        )
    finally:
        with admin.begin() as connection:
            connection.execute(
                text(update), {"tenant": TENANT_A, "person": AUDITOR, "status": "active"}
            )
        admin.dispose()


def test_grants_in_another_unit_do_not_authorize_this_audit(plan: Plan) -> None:
    x = plan
    _grant(x.records.r.db, AUDITOR, "audits.execute", UNIT_A_OTHER)
    assert summary(x).execution_authority.authorized_auditors == 0


def test_aggregate_function_never_exposes_target_grants_or_changes_actor_context(
    plan: Plan,
) -> None:
    x = plan
    _grant(x.records.r.db, AUDITOR, "audits.execute")
    set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
    hidden = text("SELECT count(*) FROM qms_access_grants WHERE user_id=:person")
    assert x.records.r.db.scalar(hidden, {"person": AUDITOR}) == 0
    result = x.records.r.db.execute(
        text("SELECT * FROM public.qms_audit_execution_authority(:id)"), {"id": x.parent}
    )
    assert list(result.keys()) == ["planned_auditors", "authorized_auditors"]
    assert tuple(result.one()) == (1, 1)
    assert x.records.r.db.scalar(hidden, {"person": AUDITOR}) == 0
    assert x.records.r.db.scalar(text("SELECT current_setting('app.user_id')")) == str(REVIEWER)
    assert (
        x.records.r.db.scalar(
            text("SELECT relforcerowsecurity FROM pg_class WHERE oid='qms_access_grants'::regclass")
        )
        is True
    )


def test_private_projection_and_trigger_are_not_runtime_entry_points(plan: Plan) -> None:
    x = plan
    for command in [
        "SELECT * FROM qms_audit_execution_grant_projection",
        "UPDATE qms_audit_execution_grant_projection SET status='active'",
        "DELETE FROM qms_audit_execution_grant_projection",
        "TRUNCATE qms_audit_execution_grant_projection",
        "SELECT public.sync_qms_audit_execution_grants()",
        "ALTER FUNCTION public.qms_audit_execution_authority(uuid) SECURITY INVOKER",
    ]:
        set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError) as denied:
            x.records.r.db.execute(text(command))
        assert denied.value.orig is not None
        assert denied.value.orig.args[0]["C"] == "42501"
        x.records.r.db.rollback()
    set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
    info = x.records.r.db.execute(
        text(
            "SELECT p.prosecdef,p.provolatile,p.proconfig,NOT EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_denied,pg_has_role(current_user,p.proowner,'MEMBER') AS can_become_owner FROM pg_proc p WHERE p.oid='public.qms_audit_execution_authority(uuid)'::regprocedure"
        )
    ).one()
    assert (
        info.prosecdef
        and info.provolatile == "s"
        and info.public_denied
        and not info.can_become_owner
    )
    assert "search_path=pg_catalog, public" in info.proconfig
    assert not x.records.r.db.scalar(
        text("SELECT has_schema_privilege(current_user,'public','CREATE')")
    )


def test_temp_shadow_objects_cannot_forge_access_results(plan: Plan) -> None:
    x = plan
    set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
    x.records.r.db.execute(
        text(
            "CREATE TEMP TABLE qms_audit_execution_grant_projection(tenant_id uuid,unit_id uuid,user_id uuid,capability text,status text) ON COMMIT DROP"
        )
    )
    for capability in ["audits.read", "audits.execute"]:
        x.records.r.db.execute(
            text(
                "INSERT INTO pg_temp.qms_audit_execution_grant_projection VALUES(:tenant,:unit,:person,:capability,'active')"
            ),
            {"tenant": TENANT_A, "unit": UNIT_A, "person": AUDITOR, "capability": capability},
        )
    x.records.r.db.execute(text("SET LOCAL search_path=pg_temp,public,pg_catalog"))
    row = x.records.r.db.execute(
        text("SELECT * FROM public.qms_audit_execution_authority(:id)"), {"id": x.parent}
    ).one()
    assert tuple(row) == (1, 0)
    x.records.r.db.rollback()


def test_projection_revocation_rolls_back_with_source_transaction(plan: Plan) -> None:
    x = plan
    grant = _grant(x.records.r.db, AUDITOR, "audits.execute")
    set_request_context(x.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    x.records.r.db.execute(
        text(
            "UPDATE qms_access_grants SET status='revoked',revoked_by_user_id=:actor,revoked_at=CURRENT_TIMESTAMP WHERE id=:id"
        ),
        {"actor": OWNER, "id": grant.id},
    )
    set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
    assert tuple(
        x.records.r.db.execute(
            text("SELECT * FROM public.qms_audit_execution_authority(:id)"), {"id": x.parent}
        ).one()
    ) == (1, 0)
    x.records.r.db.rollback()
    assert summary(x).execution_authority.status == "passed"


def test_backfill_roundtrip_preserves_review_history_and_restores_force_rls(plan: Plan) -> None:
    x = plan
    _grant(x.records.r.db, AUDITOR, "audits.execute")
    decision = record(x).review.id
    x.records.r.db.rollback()
    try:
        for command in ["downgrade", "upgrade"]:
            target = (
                "0046_audit_independence"
                if command == "downgrade"
                else "0047_audit_execution_authority"
            )
            result = subprocess.run(  # noqa: S603 -- controlled interpreter and disposable URLs.
                [sys.executable, "-m", "alembic", command, target], capture_output=True, check=False
            )
            assert result.returncode == 0, result.stderr.decode()
        after = summary(x)
        assert after.execution_authority.status == "passed" and after.review_current
        assert after.latest_review and after.latest_review.id == decision
        assert (
            x.records.r.db.scalar(
                text(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid='qms_access_grants'::regclass"
                )
            )
            is True
        )
    finally:
        # The focused0047 assertions must not leave later suites below migration head.
        x.records.r.db.rollback()
        restored = subprocess.run(  # noqa: S603 -- controlled interpreter/disposable database.
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            check=False,
        )
        assert restored.returncode == 0, restored.stderr.decode()


def test_review_revoked_during_diagnostic_returns_denial_not_database_error(
    plan: Plan, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.orm import Session

    x = plan
    set_request_context(x.records.r.db, user_id=OWNER, tenant_id=TENANT_A)
    review_grant = x.records.r.db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE user_id=:user AND capability='audits.review' AND status='active'"
        ),
        {"user": REVIEWER},
    )
    assert review_grant is not None
    x.records.r.db.commit()
    original = independence._execution_authority
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")

    def revoke_then_check(*args: Any, **kwargs: Any) -> independence.ExecutionAuthority:
        with Session(runtime) as db:
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            revoke_grant(db, _actor(OWNER, "owner"), uuid4(), review_grant)
        return original(*args, **kwargs)

    monkeypatch.setattr(independence, "_execution_authority", revoke_then_check)
    try:
        with pytest.raises(HTTPException) as denied:
            summary(x)
        assert denied.value.status_code == 403
    finally:
        runtime.dispose()


def test_an_empty_planned_roster_is_never_authorized(plan: Plan) -> None:
    x = plan
    parent = x.records.r.audits[UNIT_A][1].id
    result = independence.get_independence(parent, x.records.r.db, _authenticated(REVIEWER))
    assert result.execution_authority.status == "blocked"
    assert (
        result.execution_authority.planned_auditors,
        result.execution_authority.authorized_auditors,
    ) == (0, 0)
    assert not result.ready_for_execution


def test_private_projection_rls_still_denies_reads_if_select_were_accidentally_granted(
    plan: Plan,
) -> None:
    x = plan
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    try:
        with admin.begin() as connection:
            connection.execute(
                text("GRANT SELECT ON qms_audit_execution_grant_projection TO pmcloud_app")
            )
        set_request_context(x.records.r.db, user_id=REVIEWER, tenant_id=TENANT_A)
        assert (
            x.records.r.db.scalar(text("SELECT count(*) FROM qms_audit_execution_grant_projection"))
            == 0
        )
        assert summary(x).execution_authority.status == "blocked"
        x.records.r.db.rollback()
    finally:
        x.records.r.db.rollback()
        with admin.begin() as connection:
            connection.execute(
                text("REVOKE SELECT ON qms_audit_execution_grant_projection FROM pmcloud_app")
            )
        admin.dispose()
