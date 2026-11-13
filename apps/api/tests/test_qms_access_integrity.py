# ruff: noqa: E501
from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, context, engine

from pmc_api import audit_service
from pmc_api.database import set_request_context
from pmc_api.models import QMSAccessGrant
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import (
    GrantInput,
    active_capabilities,
    create_grant,
    require_capability,
    revoke_grant,
)

pytestmark = [
    pytest.mark.qms_access_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="QMS access suite requires disposable PostgreSQL",
    ),
]
# Reuse only disposable identity/organization seed data, not workflow test cases.


@pytest.fixture(scope="module", autouse=True)
def seed_identity() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE qms_access_grants, workflow_instance_events, workflow_instances, workflow_step_assignments, workflow_transitions, workflow_steps, workflow_versions, workflow_definitions CASCADE"
            )
        )
        connection.execute(
            text("DELETE FROM organization_unit_assignments WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM memberships WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM users WHERE id IN (:owner,:member,:other)"),
            {"owner": OWNER, "member": MEMBER, "other": OTHER},
        )
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a,:b)"), {"a": TENANT_A, "b": TENANT_B}
        )
        for tenant in (TENANT_A, TENANT_B):
            connection.execute(
                text(
                    "INSERT INTO tenants (id,name,slug,status,created_at,updated_at) VALUES (:id,:name,:slug,'active',:now,:now)"
                ),
                {"id": tenant, "name": f"Tenant {tenant}", "slug": str(tenant), "now": now},
            )
        for user in (OWNER, MEMBER, OTHER):
            connection.execute(
                text(
                    "INSERT INTO users (id,display_name,status,created_at) VALUES (:id,:name,'active',:now)"
                ),
                {"id": user, "name": str(user), "now": now},
            )
        for user, role in ((OWNER, "owner"), (MEMBER, "member"), (OTHER, "member")):
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
            {"id": uuid4(), "tenant": TENANT_B, "user": OTHER, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team','WF','Workflow team','active',:now,:now)"
            ),
            {"id": UNIT, "tenant": TENANT_A, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',true,'active',:now,:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_A, "unit": UNIT, "user": MEMBER, "now": now},
        )


@pytest.fixture(autouse=True)
def clean_grants(seed_identity: None) -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as db:
        db.execute(text("TRUNCATE qms_audit_execution_grant_projection, qms_access_grants"))


def actor(user: UUID = OWNER, role: str = "owner") -> OrganizationActor:
    return OrganizationActor(user, str(user), role, TENANT_A)


def grant_to_member(db: Session, capability: str = "documents.author") -> QMSAccessGrant:
    set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
    return create_grant(
        db, actor(), uuid4(), GrantInput(user_id=MEMBER, unit_id=UNIT, capability=capability)
    )


def test_owner_has_no_implicit_business_capability_and_empty_scope_denies() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        for scope in (UNIT, None, uuid4()):
            with pytest.raises(HTTPException) as error:
                require_capability(db, "documents.approve", scope)
            assert error.value.status_code == 403


def test_explicit_grant_is_scoped_and_cross_tenant_isolation_is_forced() -> None:
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        grant_to_member(db)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        require_capability(db, "documents.author", UNIT)
        for capability, unit in (("documents.approve", UNIT), ("documents.author", uuid4())):
            with pytest.raises(HTTPException):
                require_capability(db, capability, unit)
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        assert db.scalar(text("SELECT count(*) FROM qms_access_grants")) == 0
        with pytest.raises(HTTPException):
            require_capability(db, "documents.author", UNIT)
        assert db.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname='qms_access_grants'"
            )
        )


def test_active_capability_summary_is_complete_and_excludes_revoked_grants() -> None:
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        author = grant_to_member(db, "documents.author")
        review = grant_to_member(db, "documents.review")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert active_capabilities(db, actor(MEMBER, "member")) == [
            "documents.author",
            "documents.review",
        ]
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        revoke_grant(db, actor(), uuid4(), review.id)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert active_capabilities(db, actor(MEMBER, "member")) == ["documents.author"]
        assert author.status == "active"


def test_active_capability_summary_is_not_truncated_by_management_list_limit() -> None:
    unit_ids = [uuid4() for _ in range(101)]
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organization_units "
                "(id,tenant_id,unit_type,code,name,status,created_at,updated_at) "
                "VALUES (:id,:tenant,'team',:code,:name,'active',:now,:now)"
            ),
            [
                {
                    "id": unit_id,
                    "tenant": TENANT_A,
                    "code": f"NAV-{index:03d}",
                    "name": f"Navigation scope {index:03d}",
                    "now": now,
                }
                for index, unit_id in enumerate(unit_ids)
            ],
        )
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime) as db:
        for index, unit_id in enumerate(unit_ids):
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            create_grant(
                db,
                actor(),
                uuid4(),
                GrantInput(
                    user_id=MEMBER,
                    unit_id=unit_id,
                    capability="risks.read" if index == 0 else "documents.author",
                ),
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert active_capabilities(db, actor(MEMBER, "member")) == [
            "documents.author",
            "risks.read",
        ]


@pytest.mark.parametrize("user,role", [(MEMBER, "member"), (OWNER, "owner")])
def test_member_elevation_and_owner_self_grant_are_denied(user: UUID, role: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as error:
            create_grant(
                db,
                actor(user, role),
                uuid4(),
                GrantInput(user_id=OWNER, unit_id=UNIT, capability="documents.approve"),
            )
        assert error.value.status_code == 403


def test_member_cannot_insert_directly_through_database() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as db:
        context(db, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "INSERT INTO qms_access_grants (id,tenant_id,user_id,unit_id,capability,status,granted_by_user_id,created_at) VALUES (:id,:t,:u,:unit,'documents.approve','active',:actor,now())"
                ),
                {"id": uuid4(), "t": TENANT_A, "u": OWNER, "unit": UNIT, "actor": MEMBER},
            )


@pytest.mark.parametrize("invalid", ["target", "scope", "capability"])
def test_invalid_targets_and_capabilities_leave_no_grant(invalid: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as error:
            create_grant(
                db,
                actor(),
                uuid4(),
                GrantInput(
                    user_id=uuid4() if invalid == "target" else MEMBER,
                    unit_id=uuid4() if invalid == "scope" else UNIT,
                    capability="arbitrary.admin" if invalid == "capability" else "documents.author",
                ),
            )
        assert error.value.status_code in (409, 422)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM qms_access_grants")) == 0


def test_revocation_is_immediate_and_history_cannot_be_reactivated() -> None:
    from pmc_api.models import QMSAccessGrant

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = grant_to_member(db)
        assert isinstance(row, QMSAccessGrant)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        revoke_grant(db, actor(), uuid4(), row.id)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException):
            require_capability(db, "documents.author", UNIT)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_access_grants SET status='active',revoked_at=NULL,revoked_by_user_id=NULL WHERE id=:id"
                ),
                {"id": row.id},
            )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action='qms.access_revoked'"
                ),
                {"id": row.id},
            )
            == 1
        )


@pytest.mark.parametrize("boundary", ["user", "membership", "tenant"])
def test_revoked_identity_or_tenant_disables_existing_grants(boundary: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        grant_to_member(db)
    updates = {
        "user": ("UPDATE users SET status=:status WHERE id=:id", MEMBER, "disabled", "active"),
        "tenant": (
            "UPDATE tenants SET status=:status WHERE id=:id",
            TENANT_A,
            "disabled",
            "active",
        ),
        "membership": (
            "UPDATE memberships SET status=:status WHERE user_id=:id AND tenant_id='60000000-0000-4000-8000-000000000001'",
            MEMBER,
            "revoked",
            "active",
        ),
    }
    query, row_id, disabled, enabled = updates[boundary]
    admin = engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as db:
        db.execute(text(query), {"status": disabled, "id": row_id})
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            with pytest.raises(HTTPException):
                require_capability(db, "documents.author", UNIT)
    finally:
        with admin.begin() as db:
            db.execute(text(query), {"status": enabled, "id": row_id})


def test_audit_failure_rolls_back_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(audit_service, "record_qms_access", fail)
    with (
        Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db,
        pytest.raises(RuntimeError, match="simulated audit failure"),
    ):
        grant_to_member(db)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM qms_access_grants")) == 0


def test_duplicate_grants_are_rejected_without_duplicate_audit() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        grant_to_member(db)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        with pytest.raises(HTTPException) as error:
            grant_to_member(db)
        assert error.value.status_code == 409
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM qms_access_grants")) == 1


def test_auditor_cannot_receive_write_authority_or_retain_it_after_role_change() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        grant_to_member(db)
    admin = engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text("UPDATE memberships SET role='auditor' WHERE user_id=:user AND tenant_id=:tenant"),
            {"user": MEMBER, "tenant": TENANT_A},
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            with pytest.raises(HTTPException):
                require_capability(db, "documents.author", UNIT)
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            with pytest.raises(HTTPException) as error:
                grant_to_member(db, "documents.approve")
            assert error.value.status_code == 409
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            grant_to_member(db, "documents.read")
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            require_capability(db, "documents.read", UNIT)
    finally:
        with admin.begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET role='member' WHERE user_id=:user AND tenant_id=:tenant"
                ),
                {"user": MEMBER, "tenant": TENANT_A},
            )


def test_archived_scope_invalidates_existing_grants() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        grant_to_member(db)
    admin = engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text("UPDATE organization_unit_assignments SET status='inactive' WHERE unit_id=:unit"),
            {"unit": UNIT},
        )
        connection.execute(
            text("UPDATE organization_units SET status='archived' WHERE id=:unit"), {"unit": UNIT}
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            with pytest.raises(HTTPException):
                require_capability(db, "documents.author", UNIT)
    finally:
        with admin.begin() as connection:
            connection.execute(
                text("UPDATE organization_units SET status='active' WHERE id=:unit"), {"unit": UNIT}
            )
            connection.execute(
                text(
                    "UPDATE organization_unit_assignments SET status='active' WHERE unit_id=:unit"
                ),
                {"unit": UNIT},
            )


def test_disabled_owner_cannot_manage_or_inspect_grants_through_sql() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        grant_to_member(db)
    admin = engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(text("UPDATE users SET status='disabled' WHERE id=:id"), {"id": OWNER})
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            assert db.scalar(text("SELECT count(*) FROM qms_access_grants")) == 0
            with pytest.raises(HTTPException) as error:
                create_grant(
                    db,
                    actor(),
                    uuid4(),
                    GrantInput(user_id=MEMBER, unit_id=UNIT, capability="documents.review"),
                )
            assert error.value.status_code == 403
    finally:
        with admin.begin() as connection:
            connection.execute(text("UPDATE users SET status='active' WHERE id=:id"), {"id": OWNER})


@pytest.mark.parametrize("operation", ["delete", "rewrite"])
def test_grant_history_cannot_be_deleted_or_repurposed(operation: str) -> None:
    from pmc_api.models import QMSAccessGrant

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = grant_to_member(db)
        assert isinstance(row, QMSAccessGrant)
    query = (
        "DELETE FROM qms_access_grants WHERE id=:id"
        if operation == "delete"
        else "UPDATE qms_access_grants SET capability='documents.approve' WHERE id=:id"
    )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text(query), {"id": row.id})


@pytest.mark.parametrize("foreign", ["user", "unit"])
def test_existing_foreign_tenant_targets_are_rejected(foreign: str) -> None:
    foreign_user, foreign_unit = uuid4(), uuid4()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,display_name,status,created_at) VALUES (:id,'Foreign fixture','active',now())"
            ),
            {"id": foreign_user},
        )
        connection.execute(
            text(
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) VALUES (:id,:tenant,:user,'member','active',now())"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": foreign_user},
        )
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'site',:code,'Foreign site','active',now(),now())"
            ),
            {"id": foreign_unit, "tenant": TENANT_B, "code": uuid4().hex},
        )
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as error:
            create_grant(
                db,
                actor(),
                uuid4(),
                GrantInput(
                    user_id=foreign_user if foreign == "user" else MEMBER,
                    unit_id=foreign_unit if foreign == "unit" else UNIT,
                    capability="documents.author",
                ),
            )
        assert error.value.status_code == 409
