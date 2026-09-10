# ruff: noqa: E501

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api.database import set_request_context
from pmc_api.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTransition,
    WorkflowVersion,
)
from pmc_api.workflow_service import (
    WorkflowActor,
    publish_version,
    start_instance,
    transition_instance,
)

pytestmark = [
    pytest.mark.workflow_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="workflow suite requires disposable PostgreSQL",
    ),
]
TENANT_A = UUID("60000000-0000-4000-8000-000000000001")
TENANT_B = UUID("60000000-0000-4000-8000-000000000002")
OWNER = UUID("61000000-0000-4000-8000-000000000001")
MEMBER = UUID("61000000-0000-4000-8000-000000000002")
OTHER = UUID("61000000-0000-4000-8000-000000000003")
UNIT = UUID("62000000-0000-4000-8000-000000000001")


def engine(name: str) -> Engine:
    return create_engine(os.environ[name])


def context(connection: Connection, user: UUID, tenant: UUID | None) -> None:
    connection.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(user)})
    connection.execute(
        text("SELECT set_config('app.tenant_id', :value, true)"),
        {"value": str(tenant) if tenant else ""},
    )


@pytest.fixture(scope="module", autouse=True)
def fixtures() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE workflow_instance_events, workflow_instances, workflow_step_assignments, workflow_transitions, workflow_steps, workflow_versions, workflow_definitions CASCADE"
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


def build_published(
    role_target: str = "member",
) -> tuple[WorkflowVersion, WorkflowTransition, WorkflowStep]:
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        definition = WorkflowDefinition(
            id=uuid4(),
            tenant_id=TENANT_A,
            code=f"wf-{uuid4().hex[:8]}",
            name="Review",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(),
        )
        db.add(definition)
        db.flush()
        version = WorkflowVersion(
            id=uuid4(),
            tenant_id=TENANT_A,
            definition_id=definition.id,
            version_number=1,
            status="draft",
            created_by_user_id=OWNER,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(),
        )
        start = WorkflowStep(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            step_key="review",
            name="Review",
            step_type="task",
            is_start=True,
            position=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(),
        )
        end = WorkflowStep(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            step_key="done",
            name="Done",
            step_type="end",
            is_start=False,
            position=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(),
        )
        db.add(version)
        db.flush()
        db.add_all([start, end])
        db.flush()
        transition = WorkflowTransition(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            from_step_id=start.id,
            to_step_id=end.id,
            transition_key="approve",
            label="Approve",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(),
        )
        db.add(transition)
        db.execute(
            text(
                "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) VALUES (:id,:tenant,:version,:step,'application_role',:role,:now,:now)"
            ),
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "version": version.id,
                "step": start.id,
                "role": role_target,
                "now": datetime.now(UTC),
            },
        )
        db.commit()
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        publish_version(db, actor, uuid4(), version)
        return version, transition, start


def test_forced_rls_and_tenant_isolation() -> None:
    version, _, _ = build_published()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert connection.scalar(text("SELECT count(*) FROM workflow_versions")) == 1
        context(connection, OTHER, TENANT_B)
        assert connection.scalar(text("SELECT count(*) FROM workflow_versions")) == 0
        context(connection, OWNER, None)
        assert connection.scalar(text("SELECT count(*) FROM workflow_versions")) == 0
    assert version.status == "published"


def test_published_configuration_and_history_are_immutable() -> None:
    version, _, start = build_published()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE workflow_steps SET name='changed' WHERE id=:id"), {"id": start.id}
            )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("DELETE FROM workflow_versions WHERE id=:id"), {"id": version.id}
            )
        transaction.rollback()


def test_instance_pins_version_and_member_transition_completes() -> None:
    version, transition, _ = build_published()
    owner = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(db, owner, uuid4(), version, "Approval", None)
    member = WorkflowActor(MEMBER, str(MEMBER), "member", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        completed = transition_instance(db, member, uuid4(), instance, transition.id, 1)
        assert completed.status == "completed" and completed.row_version == 2
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM workflow_instance_events WHERE instance_id=:id AND event_type IN ('started','transitioned','completed')"
                ),
                {"id": instance.id},
            )
            == 3
        )
        with pytest.raises(HTTPException) as error:
            transition_instance(db, member, uuid4(), completed, transition.id, 1)
        assert error.value.status_code == 409


def test_assignment_and_archive_protection() -> None:
    version, _, start = build_published(role_target="member")
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        draft_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO workflow_versions (id,tenant_id,definition_id,version_number,status,created_by_user_id,created_at,updated_at) VALUES (:id,:tenant,:definition,2,'draft',:user,:now,:now)"
            ),
            {
                "id": draft_id,
                "tenant": TENANT_A,
                "definition": version.definition_id,
                "user": OWNER,
                "now": datetime.now(UTC),
            },
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO workflow_instances (id,tenant_id,workflow_version_id,title,status,current_step_id,row_version,started_by_user_id,started_at,created_at,updated_at) VALUES (:id,:tenant,:version,'bad','active',:step,1,:user,:now,:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "version": draft_id,
                    "step": start.id,
                    "user": OWNER,
                    "now": datetime.now(UTC),
                },
            )
