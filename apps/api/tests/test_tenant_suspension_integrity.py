# ruff: noqa: E501, S608
# SQL identifiers below are exclusively the constant TABLES/parametrize allowlists.
"""Suspension boundaries using only a disposable PostgreSQL and synthetic sessions.

No OIDC, customer data, application server, AV or object store is exercised.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api.database import get_db, set_request_context
from pmc_api.main import app
from pmc_api.models import Tenant
from pmc_api.tenant_access import require_tenant_access

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires the dedicated disposable tenant suspension harness",
    ),
]
A, B, SITE, B_SITE = (UUID(f"93000000-0000-4000-8000-{n:012d}") for n in range(1, 5))
USERS = {
    role: UUID(f"94000000-0000-4000-8000-{i:012d}")
    for i, role in enumerate(("owner", "admin", "member", "auditor"), 1)
}
TABLES = (
    "tenant_isolation_probes",
    "organization_units",
    "organization_unit_assignments",
    "workflow_definitions",
    "workflow_versions",
    "workflow_steps",
    "workflow_transitions",
    "workflow_step_assignments",
    "workflow_instances",
    "workflow_instance_events",
    "audit_events",
)


def context(db: Connection, user: UUID = USERS["owner"], tenant: UUID = A) -> None:
    db.execute(
        text("SELECT set_config('app.user_id',:u,true),set_config('app.tenant_id',:t,true)"),
        {"u": str(user), "t": str(tenant)},
    )


def sqlstate(error: DBAPIError) -> str:
    original = error.orig
    assert original is not None
    if original.args and isinstance(original.args[0], dict):
        return str(original.args[0].get("C", ""))
    return str(getattr(original, "sqlstate", ""))


@dataclass
class Boundary:
    admin: Engine
    runtime: Engine
    clients: dict[str, TestClient]
    definition: str = ""
    version: str = ""
    instance: str = ""
    process: str = ""

    def change(self, subject: str, active: bool) -> None:
        statements = {
            "tenant": ("UPDATE tenants SET status=:s WHERE id=:id", A),
            "user": ("UPDATE users SET status=:s WHERE id=:id", USERS["owner"]),
            "membership": (
                "UPDATE memberships SET status=:s WHERE tenant_id=:id AND user_id=:u",
                A,
            ),
        }
        statement, identifier = statements[subject]
        state = "active" if active else ("revoked" if subject == "membership" else "disabled")
        with self.admin.begin() as db:
            db.execute(text(statement), {"s": state, "id": identifier, "u": USERS["owner"]})

    def call(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        role: str = "owner",
        expected: int = 200,
    ) -> Any:
        response = self.clients[role].request(method, path, json=body)
        assert response.status_code == expected, (method, path, response.status_code, response.text)
        return response.json() if response.content else None


@pytest.fixture
def boundary() -> Iterator[Boundary]:
    admin_url, runtime_url = (
        os.environ["PMC_TEST_ADMIN_DATABASE_URL"],
        os.environ["PMC_TEST_RUNTIME_DATABASE_URL"],
    )
    assert (
        make_url(admin_url).database
        == make_url(runtime_url).database
        == "pmcloud_tenant_suspension"
    )
    admin, runtime = create_engine(admin_url), create_engine(runtime_url)
    now = datetime.now(UTC)
    with admin.begin() as db:
        db.execute(text("TRUNCATE tenants,users CASCADE"))
        for tenant, site, name in ((A, SITE, "Synthetic Alpha"), (B, B_SITE, "Synthetic Beta")):
            db.execute(
                text(
                    "INSERT INTO tenants(id,name,slug,status,created_at,updated_at) VALUES(:id,:n,:slug,'active',:now,:now)"
                ),
                {"id": tenant, "n": name, "slug": str(tenant), "now": now},
            )
            db.execute(
                text(
                    "INSERT INTO organization_units(id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES(:id,:t,'site','HQ',:n,'active',:now,:now)"
                ),
                {"id": site, "t": tenant, "n": name, "now": now},
            )
            db.execute(
                text(
                    "INSERT INTO tenant_isolation_probes(id,tenant_id,value,created_at) VALUES(:id,:t,'synthetic',:now)"
                ),
                {"id": uuid4(), "t": tenant, "now": now},
            )
        for role, user in USERS.items():
            db.execute(
                text(
                    "INSERT INTO users(id,display_name,status,created_at) VALUES(:id,:n,'active',:now)"
                ),
                {"id": user, "n": f"Synthetic {role}", "now": now},
            )
            for tenant in (A, B) if role == "owner" else (A,):
                db.execute(
                    text(
                        "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) VALUES(:id,:t,:u,:r,'active',:now)"
                    ),
                    {"id": uuid4(), "t": tenant, "u": user, "r": role, "now": now},
                )
        db.execute(
            text(
                "INSERT INTO organization_unit_assignments(id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES(:id,:t,:s,:u,'member',false,'active',:now,:now)"
            ),
            {"id": uuid4(), "t": A, "s": SITE, "u": USERS["member"], "now": now},
        )

    def override() -> Iterator[Session]:
        with Session(runtime, expire_on_commit=False) as db:
            try:
                yield db
            finally:
                db.rollback()

    app.dependency_overrides[get_db] = override
    clients: dict[str, TestClient] = {}
    try:
        for role, user in USERS.items():
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            with admin.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO application_sessions(id,user_id,token_hash,current_tenant_id,csrf_token_hash,created_at,expires_at,last_seen_at) VALUES(:id,:u,:h,:t,:c,:now,:expires,:now)"
                    ),
                    {
                        "id": uuid4(),
                        "u": user,
                        "h": hashlib.sha256(token.encode()).digest(),
                        "t": A,
                        "c": hashlib.sha256(csrf.encode()).digest(),
                        "now": now,
                        "expires": now + timedelta(hours=1),
                    },
                )
            client = TestClient(app)
            client.cookies.set("pm_session", token)
            client.cookies.set("pm_csrf", csrf)
            client.headers["X-CSRF-Token"] = csrf
            clients[role] = client
        case = Boundary(admin, runtime, clients)
        for capability in ("processes.read", "processes.manage"):
            case.call(
                "POST",
                "/qms-access/grants",
                {"user_id": str(USERS["member"]), "unit_id": str(SITE), "capability": capability},
                expected=201,
            )
        process = case.call(
            "POST",
            "/processes",
            {"unit_id": str(SITE), "code": "SYNTHETIC", "name": "Synthetic process"},
            role="member",
            expected=201,
        )
        case.process = process["id"]
        definition = case.call(
            "POST", "/workflows", {"code": "SUSPENSION", "name": "Synthetic review"}, expected=201
        )
        case.definition = definition["id"]
        version = case.call("POST", f"/workflows/{case.definition}/versions", expected=201)
        case.version = version["id"]
        start = case.call(
            "POST",
            f"/workflows/versions/{case.version}/steps",
            {
                "step_key": "review",
                "name": "Review",
                "step_type": "task",
                "is_start": True,
                "position": 0,
            },
            expected=201,
        )
        end = case.call(
            "POST",
            f"/workflows/versions/{case.version}/steps",
            {"step_key": "done", "name": "Done", "step_type": "end", "position": 1},
            expected=201,
        )
        case.call(
            "POST",
            f"/workflows/versions/{case.version}/transitions",
            {
                "from_step_id": start["id"],
                "to_step_id": end["id"],
                "transition_key": "approve",
                "label": "Approve",
            },
            expected=201,
        )
        case.call(
            "POST",
            f"/workflows/versions/{case.version}/assignments",
            {
                "step_id": start["id"],
                "target_type": "application_role",
                "target_application_role": "member",
            },
            expected=201,
        )
        case.call("POST", f"/workflows/versions/{case.version}/publish")
        instance = case.call(
            "POST",
            "/workflow-instances",
            {"workflow_version_id": case.version, "title": "Synthetic instance"},
            expected=201,
        )
        case.instance = instance["id"]
        yield case
    finally:
        app.dependency_overrides.pop(get_db, None)
        for client in clients.values():
            client.close()
        runtime.dispose()
        admin.dispose()


@pytest.mark.parametrize("table", TABLES)
def test_runtime_select_denied_after_tenant_disabled(boundary: Boundary, table: str) -> None:
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text(f"SELECT count(*) FROM {table}")) > 0
        boundary.change("tenant", False)
        # Same READ COMMITTED transaction: a later statement sees the committed suspension.
        assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.parametrize("subject", ("tenant", "user", "membership"))
def test_active_actor_required_by_directory_and_site_lock(boundary: Boundary, subject: str) -> None:
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM organization_member_directory()")) == 4
        db.execute(text("SELECT lock_qms_site_scope(:s,:t)"), {"s": SITE, "t": A})
    boundary.change(subject, False)
    with boundary.runtime.connect() as db:
        transaction = db.begin()
        context(db)
        assert db.scalar(text("SELECT count(*) FROM organization_member_directory()")) == 0
        with pytest.raises(DBAPIError) as exc:
            db.execute(text("SELECT lock_qms_site_scope(:s,:t)"), {"s": SITE, "t": A})
        assert sqlstate(exc.value) == "42501"
        transaction.rollback()
    boundary.change(subject, True)
    with boundary.runtime.begin() as db:
        context(db)
        db.execute(text("SELECT lock_qms_site_scope(:s,:t)"), {"s": SITE, "t": A})


def test_http_business_reads_and_writes_suspend_without_mutation(boundary: Boundary) -> None:
    reads = [
        "/organization/units",
        "/organization/assignments",
        "/organization/members",
        "/audit/events",
        "/workflows",
        f"/workflows/{boundary.definition}/versions",
        f"/workflows/versions/{boundary.version}/steps",
        f"/workflows/versions/{boundary.version}/transitions",
        f"/workflows/versions/{boundary.version}/assignments",
        "/workflow-instances",
        f"/workflow-instances/{boundary.instance}/history",
    ]
    for path in reads:
        boundary.call("GET", path)
    with boundary.admin.begin() as db:
        before = {table: db.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES}
    boundary.change("tenant", False)
    for path in reads:
        boundary.call("GET", path, expected=403)
    boundary.call(
        "PATCH", f"/organization/units/{SITE}", {"name": "Unauthorized edit"}, expected=403
    )
    boundary.call(
        "POST",
        "/organization/units",
        {"unit_type": "team", "code": "NO", "name": "Blocked"},
        expected=403,
    )
    boundary.call("POST", "/workflows", {"code": "NO", "name": "Blocked"}, expected=403)
    boundary.call("POST", f"/workflows/{boundary.definition}/versions", expected=403)
    boundary.call(
        "POST",
        "/workflow-instances",
        {"workflow_version_id": boundary.version, "title": "Blocked"},
        expected=403,
    )
    boundary.call(
        "POST",
        f"/workflow-instances/{boundary.instance}/cancel",
        {"reason": "Blocked"},
        expected=403,
    )
    with boundary.admin.begin() as db:
        assert before == {
            table: db.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES
        }
        assert (
            db.scalar(text("SELECT name FROM organization_units WHERE id=:id"), {"id": SITE})
            == "Synthetic Alpha"
        )


@pytest.mark.parametrize("subject,expected", [("tenant", 403), ("membership", 403), ("user", 401)])
def test_http_actor_revocation_and_reactivation(
    boundary: Boundary, subject: str, expected: int
) -> None:
    boundary.change(subject, False)
    boundary.call("GET", "/organization/units", expected=expected)
    boundary.call("GET", "/audit/events", expected=expected)
    boundary.change(subject, True)
    assert len(boundary.call("GET", "/organization/units")) == 1
    boundary.call("PATCH", f"/organization/units/{SITE}", {"name": "Restored authority"})
    boundary.call(
        "PATCH",
        f"/organization/units/{SITE}",
        {"name": "No member privilege"},
        role="member",
        expected=403,
    )
    boundary.call(
        "POST",
        "/qms-access/grants",
        {"user_id": str(USERS["member"]), "unit_id": str(SITE), "capability": "processes.read"},
        role="admin",
        expected=403,
    )


def test_session_recovery_and_other_company_are_preserved(boundary: Boundary) -> None:
    boundary.change("tenant", False)
    assert boundary.call("GET", "/auth/me")["current_tenant_id"] == str(A)
    assert [row["id"] for row in boundary.call("GET", "/auth/tenants")] == [str(B)]
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(A)}, expected=403)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)}, role="member", expected=403)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    assert [row["id"] for row in boundary.call("GET", "/organization/units")] == [str(B_SITE)]
    with boundary.runtime.begin() as db:
        context(db, tenant=B)
        assert (
            db.scalar(text("SELECT count(*) FROM organization_units WHERE tenant_id=:t"), {"t": A})
            == 0
        )
        assert db.scalar(text("SELECT count(*) FROM organization_units")) == 1
    boundary.call("POST", "/auth/logout", expected=204)
    boundary.call("GET", "/auth/me", expected=401)


def test_same_session_does_not_authorize_from_cached_tenant(boundary: Boundary) -> None:
    with Session(boundary.runtime, expire_on_commit=False) as db:
        set_request_context(db, user_id=USERS["owner"], tenant_id=A)
        tenant = db.get(Tenant, A)
        assert tenant is not None and tenant.status == "active"
        assert require_tenant_access(db, user_id=USERS["owner"], tenant_id=A).role == "owner"
        transaction = db.get_transaction()
        boundary.change("tenant", False)
        assert tenant.status == "active"  # Deliberately stale identity map.
        with pytest.raises(HTTPException) as exc:
            require_tenant_access(db, user_id=USERS["owner"], tenant_id=A)
        assert exc.value.status_code == 403
        assert db.get_transaction() is transaction
        assert db.scalar(text("SELECT count(*) FROM organization_units")) == 0
        boundary.change("tenant", True)
        assert require_tenant_access(db, user_id=USERS["owner"], tenant_id=A).role == "owner"
        assert db.scalar(text("SELECT count(*) FROM organization_units")) == 1


@pytest.mark.parametrize("table", ["organization_units", "workflow_definitions"])
def test_sql_updates_and_inserts_fail_closed(boundary: Boundary, table: str) -> None:
    boundary.change("tenant", False)
    with boundary.runtime.begin() as db:
        context(db)
        assert db.execute(text(f"UPDATE {table} SET name=name")).rowcount == 0
    statement = {
        "organization_units": "INSERT INTO organization_units(id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES(:id,:t,'team','DENIED','Blocked','active',now(),now())",
        "workflow_definitions": "INSERT INTO workflow_definitions(id,tenant_id,code,name,status,created_at,updated_at) VALUES(:id,:t,'DENIED','Blocked','active',now(),now())",
    }[table]
    with boundary.runtime.connect() as db:
        transaction = db.begin()
        context(db)
        with pytest.raises(DBAPIError) as exc:
            db.execute(text(statement), {"id": uuid4(), "t": A})
        assert sqlstate(exc.value) == "42501"
        transaction.rollback()


def test_policy_and_runtime_privileges_do_not_expand(boundary: Boundary) -> None:
    with boundary.runtime.begin() as db:
        context(db)
        rows = db.execute(
            text(
                "SELECT tablename,permissive,roles,cmd FROM pg_policies WHERE policyname='tenant_active_guard' ORDER BY tablename"
            )
        ).all()
        assert {row.tablename for row in rows} == set(TABLES)
        assert all(
            row.permissive == "RESTRICTIVE" and row.cmd == "ALL" and row.roles == ["pmcloud_app"]
            for row in rows
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM pg_policies WHERE tablename='organization_units' AND permissive='PERMISSIVE'"
                )
            )
            > 0
        )
        assert db.execute(
            text(
                "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user"
            )
        ).one() == (False, False, False, False)
        assert not db.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')"))
        assert not db.scalar(text("SELECT has_table_privilege(current_user,'tenants','UPDATE')"))
        assert not db.scalar(
            text("SELECT has_table_privilege(current_user,'memberships','UPDATE')")
        )
        assert not db.scalar(
            text("SELECT has_table_privilege(current_user,'audit_events','UPDATE,DELETE,TRUNCATE')")
        )
        assert db.scalar(
            text(
                "SELECT has_function_privilege(current_user,'lock_qms_site_scope(uuid,uuid)','EXECUTE')"
            )
        )


def migrate(target: str, direction: str = "upgrade") -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed Alembic command, controlled revision constants
        [sys.executable, "-m", "alembic", direction, target],
        capture_output=True,
        text=True,
        check=False,
    )


def test_downgrade_refuses_disabled_companies_and_rolls_back_ddl(boundary: Boundary) -> None:
    boundary.change("tenant", False)
    result = migrate("0048_audit_competence", "downgrade")
    assert result.returncode != 0
    assert "cannot remove tenant suspension guards with disabled companies" in result.stderr
    assert "55000" in result.stderr
    with boundary.admin.begin() as db:
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version")) == "0049_tenant_suspension"
        )
        assert db.scalar(
            text("SELECT relforcerowsecurity FROM pg_class WHERE oid='tenants'::regclass")
        )
        assert db.scalar(
            text("SELECT count(*) FROM pg_policies WHERE policyname='tenant_active_guard'")
        ) == len(TABLES)
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM organization_units")) == 0


def test_active_history_roundtrip_preserves_rows_and_acl(boundary: Boundary) -> None:
    def snapshot() -> tuple[Any, ...]:
        with boundary.admin.begin() as db:
            return (
                tuple(db.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES),
                tuple(
                    db.execute(
                        text(
                            "SELECT proname,proowner,proacl,pg_get_functiondef(oid) FROM pg_proc WHERE proname IN ('organization_member_directory','lock_qms_site_scope') ORDER BY proname"
                        )
                    ).all()
                ),
            )

    before = snapshot()
    boundary.runtime.dispose()
    result = migrate("0048_audit_competence", "downgrade")
    try:
        assert result.returncode == 0, result.stderr
    finally:
        restored = migrate("head")
        assert restored.returncode == 0, restored.stderr
    assert snapshot() == before
    boundary.change("tenant", False)
    boundary.call("GET", "/organization/units", expected=403)
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM organization_units")) == 0


@pytest.mark.parametrize("subject", ("user", "membership"))
def test_all_legacy_sql_reads_reject_inactive_actor(boundary: Boundary, subject: str) -> None:
    boundary.change(subject, False)
    with boundary.runtime.begin() as db:
        context(db)
        for table in TABLES:
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    boundary.change(subject, True)
    with boundary.runtime.begin() as db:
        context(db)
        for table in TABLES:
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) > 0


def test_qms_grants_and_original_scope_survive_suspension(boundary: Boundary) -> None:
    # Real, scoped QMS record: a 200/empty listing cannot conceal a missing fixture.
    records = boundary.call("GET", "/processes", role="member")
    assert [row["id"] for row in records] == [boundary.process]
    with boundary.admin.begin() as db:
        before = db.execute(
            text("SELECT id,user_id,unit_id,capability,status FROM qms_access_grants ORDER BY id")
        ).all()
    boundary.change("tenant", False)
    boundary.call("GET", "/processes", role="member", expected=403)
    boundary.call("GET", f"/processes/{boundary.process}", role="member", expected=403)
    boundary.change("tenant", True)
    assert [row["id"] for row in boundary.call("GET", "/processes", role="member")] == [
        boundary.process
    ]
    with boundary.admin.begin() as db:
        assert (
            db.execute(
                text(
                    "SELECT id,user_id,unit_id,capability,status FROM qms_access_grants ORDER BY id"
                )
            ).all()
            == before
        )
    # Company owner is still not granted implicit QMS authority.
    assert boundary.call("GET", "/processes") == []


def test_direct_ledger_insert_cannot_bypass_suspension(boundary: Boundary) -> None:
    boundary.change("tenant", False)
    with boundary.runtime.connect() as db:
        transaction = db.begin()
        context(db)
        with pytest.raises(DBAPIError) as exc:
            db.execute(
                text(
                    "INSERT INTO audit_events(id,tenant_id,occurred_at,actor_user_id,actor_display_name,actor_role,action,resource_type,resource_id,request_id,schema_version,changed_fields,old_values,new_values,metadata) VALUES(:id,:t,now(),:u,'Synthetic owner','owner','tenant.selected','tenant',:t,:request,1,'[]',NULL,NULL,'{}')"
                ),
                {"id": uuid4(), "t": A, "u": USERS["owner"], "request": uuid4()},
            )
        assert sqlstate(exc.value) == "42501"
        transaction.rollback()


@pytest.mark.parametrize("operation", ("create", "revoke"))
def test_service_rechecks_owner_role_after_membership_downgrade(
    boundary: Boundary, operation: str
) -> None:
    from pmc_api.organization_service import OrganizationActor
    from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

    stale = OrganizationActor(USERS["owner"], "Synthetic owner", "owner", A)
    with boundary.admin.begin() as connection:
        grants_before = connection.execute(
            text("SELECT id,user_id,capability,status FROM qms_access_grants ORDER BY id")
        ).all()
        events_before = connection.scalar(text("SELECT count(*) FROM audit_events"))
        connection.execute(
            text("UPDATE memberships SET role='member' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["owner"]},
        )
    with Session(boundary.runtime, expire_on_commit=False) as db:
        set_request_context(db, user_id=USERS["owner"], tenant_id=A)
        with pytest.raises(HTTPException) as exc:
            if operation == "create":
                create_grant(
                    db,
                    stale,
                    uuid4(),
                    GrantInput(user_id=USERS["member"], unit_id=SITE, capability="documents.read"),
                )
            else:
                revoke_grant(db, stale, uuid4(), grants_before[0].id)
        assert exc.value.status_code == 403
        db.rollback()
    with boundary.admin.begin() as connection:
        assert (
            connection.execute(
                text("SELECT id,user_id,capability,status FROM qms_access_grants ORDER BY id")
            ).all()
            == grants_before
        )
        assert connection.scalar(text("SELECT count(*) FROM audit_events")) == events_before
