# ruff: noqa: E501

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = [
    pytest.mark.organization_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="organization integrity suite requires disposable PostgreSQL",
    ),
]
TENANT_A = UUID("30000000-0000-4000-8000-000000000001")
TENANT_B = UUID("30000000-0000-4000-8000-000000000002")
OWNER = UUID("40000000-0000-4000-8000-000000000001")
ADMIN = UUID("40000000-0000-4000-8000-000000000002")
AUDITOR = UUID("40000000-0000-4000-8000-000000000003")
MEMBER = UUID("40000000-0000-4000-8000-000000000004")
ROOT = UUID("50000000-0000-4000-8000-000000000001")
CHILD = UUID("50000000-0000-4000-8000-000000000002")


def engine(name: str, **kwargs: object) -> Engine:
    return create_engine(os.environ[name], **kwargs)


def context(connection: Connection, user: UUID, tenant: UUID | None) -> None:
    connection.execute(text("SELECT set_config('app.user_id', :user, true)"), {"user": str(user)})
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"),
        {"tenant": str(tenant) if tenant else ""},
    )


@pytest.fixture(scope="module", autouse=True)
def fixtures() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("TRUNCATE organization_unit_assignments, organization_units CASCADE")
        )
        connection.execute(
            text("DELETE FROM memberships WHERE tenant_id IN (:a, :b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM users WHERE id IN (:owner, :admin, :auditor, :member)"),
            {"owner": OWNER, "admin": ADMIN, "auditor": AUDITOR, "member": MEMBER},
        )
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": TENANT_A, "b": TENANT_B}
        )
        for tenant, name in ((TENANT_A, "Organization A"), (TENANT_B, "Organization B")):
            connection.execute(
                text(
                    "INSERT INTO tenants (id,name,slug,status,created_at,updated_at) VALUES (:id,:name,:slug,'active',:now,:now)"
                ),
                {"id": tenant, "name": name, "slug": str(tenant), "now": now},
            )
        for user, name in (
            (OWNER, "Owner"),
            (ADMIN, "Admin"),
            (AUDITOR, "Auditor"),
            (MEMBER, "Member"),
        ):
            connection.execute(
                text(
                    "INSERT INTO users (id,display_name,status,created_at) VALUES (:id,:name,'active',:now)"
                ),
                {"id": user, "name": name, "now": now},
            )
        for user, role in (
            (OWNER, "owner"),
            (ADMIN, "admin"),
            (AUDITOR, "auditor"),
            (MEMBER, "member"),
        ):
            connection.execute(
                text(
                    "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) VALUES (:id,:tenant,:user,:role,'active',:now)"
                ),
                {"id": uuid4(), "tenant": TENANT_A, "user": user, "role": role, "now": now},
            )
        connection.execute(
            text(
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) VALUES (:id,:tenant,:user,'member','active',:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": MEMBER, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'site','ROOT','Root','active',:now,:now)"
            ),
            {"id": ROOT, "tenant": TENANT_A, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,parent_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,:parent,'department','CHILD','Child','active',:now,:now)"
            ),
            {"id": CHILD, "tenant": TENANT_A, "parent": ROOT, "now": now},
        )


def test_all_active_roles_read_and_tenant_isolation() -> None:
    for user in (OWNER, ADMIN, AUDITOR, MEMBER):
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
            context(connection, user, TENANT_A)
            assert connection.scalar(text("SELECT count(*) FROM organization_units")) == 2
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM organization_units WHERE tenant_id = :tenant"),
                    {"tenant": TENANT_B},
                )
                == 0
            )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, MEMBER, TENANT_B)
        assert connection.scalar(text("SELECT count(*) FROM organization_units")) == 0


def test_hierarchy_self_parent_cycle_cross_tenant_and_archived_parent() -> None:
    attempts = [
        ("UPDATE organization_units SET parent_id = id WHERE id = :id", {"id": ROOT}),
        (
            "UPDATE organization_units SET parent_id = :parent WHERE id = :id",
            {"parent": CHILD, "id": ROOT},
        ),
        (
            "INSERT INTO organization_units (id,tenant_id,parent_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,:parent,'team','BAD','Bad','active',:now,:now)",
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "parent": UUID("50000000-0000-4000-8000-000000000099"),
                "now": datetime.now(UTC),
            },
        ),
    ]
    for sql, params in attempts:
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            transaction = connection.begin()
            context(connection, OWNER, TENANT_A)
            with pytest.raises(DBAPIError):
                connection.execute(text(sql), params)  # type: ignore[call-overload]
            transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("UPDATE organization_units SET parent_id=NULL WHERE id=:id"), {"id": CHILD}
        )
        connection.execute(
            text("UPDATE organization_units SET status='archived' WHERE id=:id"), {"id": CHILD}
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE organization_units SET parent_id=:parent WHERE id=:id"),
                {"parent": CHILD, "id": ROOT},
            )


def test_case_insensitive_code_and_archive_dependencies() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'site','root','Duplicate','active',:now,:now)"
                ),
                {"id": uuid4(), "tenant": TENANT_A, "now": datetime.now(UTC)},
            )
        transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE organization_units SET status='archived' WHERE id=:id"), {"id": ROOT}
            )
        transaction.rollback()


def test_assignments_require_active_membership_and_unique_primary() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'lead',true,'active',:now,:now)"
            ),
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "unit": ROOT,
                "user": MEMBER,
                "now": datetime.now(UTC),
            },
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',true,'active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "unit": ROOT,
                    "user": MEMBER,
                    "now": datetime.now(UTC),
                },
            )
        transaction.rollback()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        connection.execute(text("SET LOCAL app.organization_test = 'primary'"))
        transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": MEMBER},
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',false,'active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "unit": ROOT,
                    "user": MEMBER,
                    "now": datetime.now(UTC),
                },
            )
        transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": MEMBER},
        )


def test_owner_admin_write_and_auditor_member_denial() -> None:
    for user in (OWNER, ADMIN):
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
            context(connection, user, TENANT_A)
            connection.execute(
                text(
                    "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team',:code,'Writable','active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "code": str(uuid4())[:8],
                    "now": datetime.now(UTC),
                },
            )
    for user in (AUDITOR, MEMBER):
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            transaction = connection.begin()
            context(connection, user, TENANT_A)
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team',:code,'Denied','active',:now,:now)"
                    ),
                    {
                        "id": uuid4(),
                        "tenant": TENANT_A,
                        "code": str(uuid4())[:8],
                        "now": datetime.now(UTC),
                    },
                )
            transaction.rollback()


def test_forced_rls_no_delete_and_pool_context_reset() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        row = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='organization_units'::regclass"
            )
        ).one()
        assert tuple(row) == (True, True)
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text("DELETE FROM organization_units WHERE id=:id"), {"id": ROOT})
        transaction.rollback()
    pooled = engine("PMC_TEST_RUNTIME_DATABASE_URL", pool_size=1, max_overflow=0)
    with pooled.begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert connection.scalar(text("SELECT count(*) FROM organization_units")) > 0
    with pooled.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM organization_units")) == 0


def test_audit_and_membership_role_separation() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        before = connection.scalar(
            text("SELECT role FROM memberships WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": OWNER},
        )
        connection.execute(
            text(
                "INSERT INTO audit_events (id,tenant_id,actor_user_id,actor_display_name,actor_role,action,resource_type,resource_id,request_id,schema_version,changed_fields,new_values,metadata) VALUES (:id,:tenant,:user,'Owner','owner','organization.unit_updated','organization_unit',:resource,:request,1,'[]'::jsonb,'{}'::jsonb,'{}'::jsonb)"
            ),
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "user": OWNER,
                "resource": ROOT,
                "request": uuid4(),
            },
        )
        after = connection.scalar(
            text("SELECT role FROM memberships WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": OWNER},
        )
        assert before == after == "owner"
