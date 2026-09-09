# ruff: noqa: E501

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

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
B_MEMBER = UUID("40000000-0000-4000-8000-000000000005")
DISABLED_MEMBER = UUID("40000000-0000-4000-8000-000000000006")
ROOT = UUID("50000000-0000-4000-8000-000000000001")
CHILD = UUID("50000000-0000-4000-8000-000000000002")
B_UNIT = UUID("50000000-0000-4000-8000-000000000003")
ARCHIVED_UNIT = UUID("50000000-0000-4000-8000-000000000004")


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
            text(
                "DELETE FROM users WHERE id IN (:owner, :admin, :auditor, :member, :b_member, :disabled_member)"
            ),
            {
                "owner": OWNER,
                "admin": ADMIN,
                "auditor": AUDITOR,
                "member": MEMBER,
                "b_member": B_MEMBER,
                "disabled_member": DISABLED_MEMBER,
            },
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
            (B_MEMBER, "Tenant B Member"),
            (DISABLED_MEMBER, "Disabled Member"),
        ):
            connection.execute(
                text(
                    "INSERT INTO users (id,display_name,status,created_at) VALUES (:id,:name,:status,:now)"
                ),
                {
                    "id": user,
                    "name": name,
                    "status": "disabled" if user == DISABLED_MEMBER else "active",
                    "now": now,
                },
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
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) "
                "VALUES (:id,:tenant,:user,'member','active',:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": B_MEMBER, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) "
                "VALUES (:id,:tenant,:user,'member','active',:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_A, "user": DISABLED_MEMBER, "now": now},
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
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) "
                "VALUES (:id,:tenant,'site','B-ROOT','Tenant B root','active',:now,:now)"
            ),
            {"id": B_UNIT, "tenant": TENANT_B, "now": now},
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
        context(connection, B_MEMBER, TENANT_B)
        assert connection.scalar(text("SELECT count(*) FROM organization_units")) == 1


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
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        connection.execute(
            text("UPDATE organization_units SET parent_id=NULL WHERE id=:id"), {"id": CHILD}
        )
        connection.execute(
            text("UPDATE organization_units SET status='archived' WHERE id=:id"), {"id": CHILD}
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_units (id,tenant_id,parent_id,unit_type,code,name,status,created_at,updated_at) "
                    "VALUES (:id,:tenant,:parent,'team','ARCHIVED-PARENT','Blocked','active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "parent": CHILD,
                    "now": datetime.now(UTC),
                },
            )
        transaction.rollback()


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
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_policies WHERE policyname='memberships_organization_assignment_validation'"
                )
            )
            == 0
        )
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
        after = connection.scalar(
            text("SELECT role FROM memberships WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": OWNER},
        )
        assert before == after == "owner"


def test_directory_is_current_tenant_active_safe_projection() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        rows = connection.execute(
            text("SELECT user_id, display_name, role FROM organization_member_directory()")
        ).all()
        assert {row[0] for row in rows} == {OWNER, ADMIN, AUDITOR, MEMBER}
        assert all(len(row) == 3 for row in rows)
        assert all("@" not in str(value) for row in rows for value in row[1:2])
        assert all(row[0] != B_MEMBER for row in rows)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": MEMBER},
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
                {"user": MEMBER},
            )
            == 0
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": MEMBER},
        )


def test_directory_separates_membership_and_user_status_lifecycles() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        projection = connection.execute(
            text(
                "SELECT membership_status, user_status, role "
                "FROM organization_member_directory_projection "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": DISABLED_MEMBER},
        ).one()
        assert tuple(projection) == ("active", "disabled", "member")
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
                {"user": DISABLED_MEMBER},
            )
            == 0
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET display_name='Re-enabled Member', status='active' WHERE id=:user"
            ),
            {"user": DISABLED_MEMBER},
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT display_name FROM organization_member_directory() WHERE user_id=:user"),
                {"user": DISABLED_MEMBER},
            )
            == "Re-enabled Member"
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET display_name='Disabled Member', status='disabled' WHERE id=:user"
            ),
            {"user": DISABLED_MEMBER},
        )
        membership = connection.execute(
            text("SELECT status, role FROM memberships WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": DISABLED_MEMBER},
        ).one()
        assert tuple(membership) == ("active", "member")
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
                {"user": DISABLED_MEMBER},
            )
            == 0
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("UPDATE users SET status='active' WHERE id=:user"), {"user": DISABLED_MEMBER}
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
                {"user": DISABLED_MEMBER},
            )
            == 1
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": DISABLED_MEMBER},
        )
        connection.execute(
            text("UPDATE users SET status='disabled' WHERE id=:user"), {"user": DISABLED_MEMBER}
        )
        connection.execute(
            text("UPDATE users SET status='active' WHERE id=:user"), {"user": DISABLED_MEMBER}
        )
        final_state = connection.execute(
            text(
                "SELECT membership_status, user_status "
                "FROM organization_member_directory_projection "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": DISABLED_MEMBER},
        ).one()
        assert tuple(final_state) == ("revoked", "active")
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_member_directory() WHERE user_id=:user"),
                {"user": DISABLED_MEMBER},
            )
            == 0
        )


def test_disabled_user_assignments_are_denied_without_hard_delete() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        inactive = uuid4()
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments "
                "(id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) "
                "VALUES (:id,:tenant,:unit,:user,'member',false,'inactive',:now,:now)"
            ),
            {
                "id": inactive,
                "tenant": TENANT_A,
                "unit": ROOT,
                "user": DISABLED_MEMBER,
                "now": now,
            },
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments "
                    "(id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) "
                    "VALUES (:id,:tenant,:unit,:user,'member',false,'active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "unit": ROOT,
                    "user": DISABLED_MEMBER,
                    "now": now,
                },
            )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE organization_unit_assignments SET status='active' WHERE id=:id"),
                {"id": inactive},
            )
        transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_unit_assignments WHERE id=:id"),
                {"id": inactive},
            )
            == 1
        )


def test_projection_tables_are_not_runtime_readable() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT user_id FROM organization_member_directory_projection"))
        transaction.rollback()


def test_raw_target_guc_cannot_bypass_membership_isolation() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(TENANT_B)}
        )
        connection.execute(
            text("SELECT set_config('app.organization_target_user', :user, true)"),
            {"user": str(B_MEMBER)},
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM memberships WHERE tenant_id=:tenant"),
                {"tenant": TENANT_B},
            )
            == 0
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, UUID(int=0), None)
        assert connection.scalar(text("SELECT count(*) FROM memberships")) == 0
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": OWNER},
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM memberships WHERE tenant_id=:tenant"),
                {"tenant": TENANT_A},
            )
            == 0
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": TENANT_A, "user": OWNER},
        )


def test_real_cross_tenant_parent_and_assignment_boundaries() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_units WHERE id=:id"), {"id": B_UNIT}
            )
            == 0
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE organization_units SET parent_id=:parent WHERE id=:id"),
                {"parent": B_UNIT, "id": ROOT},
            )
        transaction.rollback()
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
                    "unit": B_UNIT,
                    "user": MEMBER,
                    "now": datetime.now(UTC),
                },
            )
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',false,'active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "unit": ROOT,
                    "user": B_MEMBER,
                    "now": datetime.now(UTC),
                },
            )
        transaction.rollback()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        a_assignment = uuid4()
        b_assignment = uuid4()
        now = datetime.now(UTC)
        for assignment, tenant, unit, user in (
            (a_assignment, TENANT_A, ROOT, MEMBER),
            (b_assignment, TENANT_B, B_UNIT, B_MEMBER),
        ):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',false,'active',:now,:now)"
                ),
                {"id": assignment, "tenant": tenant, "unit": unit, "user": user, "now": now},
            )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_unit_assignments WHERE id=:id"),
                {"id": b_assignment},
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_unit_assignments WHERE id=:id"),
                {"id": a_assignment},
            )
            == 1
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, B_MEMBER, TENANT_B)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_unit_assignments WHERE id=:id"),
                {"id": a_assignment},
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM organization_unit_assignments WHERE id=:id"),
                {"id": b_assignment},
            )
            == 1
        )


def test_archived_unit_rejects_create_and_reactivation() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team','ARCHIVED','Archived','archived',:now,:now)"
            ),
            {"id": ARCHIVED_UNIT, "tenant": TENANT_A, "now": now},
        )
        inactive = uuid4()
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',false,'inactive',:now,:now)"
            ),
            {"id": inactive, "tenant": TENANT_A, "unit": ARCHIVED_UNIT, "user": MEMBER, "now": now},
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
                    "unit": ARCHIVED_UNIT,
                    "user": MEMBER,
                    "now": now,
                },
            )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE organization_unit_assignments SET status='active' WHERE id=:id"),
                {"id": inactive},
            )
        transaction.rollback()


def test_lead_assignment_does_not_escalate_application_role() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'lead',false,'active',:now,:now)"
            ),
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "unit": CHILD,
                "user": MEMBER,
                "now": datetime.now(UTC),
            },
        )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert (
            connection.scalar(
                text("SELECT role FROM memberships WHERE tenant_id=:tenant AND user_id=:user"),
                {"tenant": TENANT_A, "user": MEMBER},
            )
            == "member"
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team','LEAD-DENIED','Denied','active',:now,:now)"
                ),
                {"id": uuid4(), "tenant": TENANT_A, "now": datetime.now(UTC)},
            )
        transaction.rollback()


def test_organization_service_audit_atomicity_and_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pmc_api import audit_service
    from pmc_api.database import set_request_context
    from pmc_api.organization_service import create_unit, require_context, update_unit

    request_id = uuid4()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as session:
        set_request_context(session, user_id=OWNER, tenant_id=TENANT_A)
        actor = require_context(session, user_id=OWNER, tenant_id=TENANT_A)
        unit = create_unit(
            session,
            actor=actor,
            request_id=request_id,
            values={"unit_type": "team", "code": str(uuid4())[:8], "name": "Atomic"},
        )
        set_request_context(session, user_id=OWNER, tenant_id=TENANT_A)
        update_unit(
            session,
            actor=actor,
            request_id=request_id,
            unit=unit,
            changes={"name": "Atomic Updated"},
        )
        set_request_context(session, user_id=OWNER, tenant_id=TENANT_A)
        assert (
            session.scalar(
                text("SELECT count(*) FROM audit_events WHERE request_id=:id"), {"id": request_id}
            )
            == 2
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM organization_units WHERE id=:id"), {"id": unit.id}
            )
            == 1
        )
    failed_id = uuid4()
    original = audit_service.record_organization_unit_created
    monkeypatch.setattr(
        audit_service,
        "record_organization_unit_created",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit failure")),
    )
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as session:
        set_request_context(session, user_id=OWNER, tenant_id=TENANT_A)
        actor = require_context(session, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(RuntimeError):
            create_unit(
                session,
                actor=actor,
                request_id=failed_id,
                values={"unit_type": "team", "code": str(uuid4())[:8], "name": "Rolled Back"},
            )
        session.rollback()
        assert (
            session.scalar(
                text("SELECT count(*) FROM audit_events WHERE request_id=:id"), {"id": failed_id}
            )
            == 0
        )
    monkeypatch.setattr(audit_service, "record_organization_unit_created", original)
    duplicate_id = uuid4()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as session:
        set_request_context(session, user_id=OWNER, tenant_id=TENANT_A)
        actor = require_context(session, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            create_unit(
                session,
                actor=actor,
                request_id=duplicate_id,
                values={"unit_type": "team", "code": "ROOT", "name": "Constraint"},
            )
        session.rollback()
        assert (
            session.scalar(
                text("SELECT count(*) FROM audit_events WHERE request_id=:id"), {"id": duplicate_id}
            )
            == 0
        )


def test_organization_audit_contract_rejects_extra_fields() -> None:
    from pmc_api.audit_service import AuditPayloadError, record_organization_unit_created

    with (
        Session(engine("PMC_TEST_ADMIN_DATABASE_URL")) as session,
        pytest.raises(AuditPayloadError),
    ):
        record_organization_unit_created(
            session,
            tenant_id=TENANT_A,
            actor_user_id=OWNER,
            actor_display_name="Owner",
            actor_role="owner",
            resource_id=ROOT,
            request_id=uuid4(),
            new_values={"unit_id": str(ROOT), "internal_note": "reject"},
        )
