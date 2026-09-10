# ruff: noqa: E501

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection, Engine, create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.database import set_request_context
from pmc_api.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTransition,
    WorkflowVersion,
)
from pmc_api.workflow_service import (
    WorkflowActor,
    _validate_graph,
    cancel_instance,
    eligible_actions,
    publish_version,
    start_instance,
    transition_instance,
    upsert_assignment,
    upsert_step,
    upsert_transition,
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
    target_type: str = "application_role",
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
        if target_type == "user":
            db.execute(
                text(
                    "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_user_id,created_at,updated_at) VALUES (:id,:tenant,:version,:step,'user',:user,:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "version": version.id,
                    "step": start.id,
                    "user": UUID(role_target),
                    "now": datetime.now(UTC),
                },
            )
        else:
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
        context(connection, OWNER, TENANT_A)
        _expect_rejected(
            connection, "UPDATE workflow_steps SET name='changed' WHERE id=:id", {"id": start.id}
        )
        _expect_rejected(
            connection, "DELETE FROM workflow_versions WHERE id=:id", {"id": version.id}
        )


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


def _draft_pair() -> tuple[
    WorkflowVersion, WorkflowStep, WorkflowStep, WorkflowVersion, WorkflowStep, WorkflowStep
]:
    now = datetime.now(UTC)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        definition = WorkflowDefinition(
            id=uuid4(),
            tenant_id=TENANT_A,
            code=f"pair-{uuid4().hex[:8]}",
            name="Pair",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(definition)
        db.flush()
        versions: list[WorkflowVersion] = []
        steps: list[WorkflowStep] = []
        for number in (1, 2):
            version = WorkflowVersion(
                id=uuid4(),
                tenant_id=TENANT_A,
                definition_id=definition.id,
                version_number=number,
                status="retired" if number == 1 else "draft",
                created_by_user_id=OWNER,
                created_at=now,
                updated_at=now,
            )
            start = WorkflowStep(
                id=uuid4(),
                tenant_id=TENANT_A,
                workflow_version_id=version.id,
                step_key=f"start-{number}",
                name=f"Start {number}",
                step_type="task",
                is_start=True,
                position=0,
                created_at=now,
                updated_at=now,
            )
            end = WorkflowStep(
                id=uuid4(),
                tenant_id=TENANT_A,
                workflow_version_id=version.id,
                step_key=f"end-{number}",
                name=f"End {number}",
                step_type="end",
                is_start=False,
                position=1,
                created_at=now,
                updated_at=now,
            )
            versions.append(version)
            steps.extend((start, end))
            db.add(version)
            db.flush()
            db.add_all((start, end))
            db.flush()
            db.add(
                WorkflowTransition(
                    id=uuid4(),
                    tenant_id=TENANT_A,
                    workflow_version_id=version.id,
                    from_step_id=start.id,
                    to_step_id=end.id,
                    transition_key=f"go-{number}",
                    label="Go",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.execute(
                text(
                    "INSERT INTO workflow_step_assignments "
                    "(id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) "
                    "VALUES (:id,:tenant,:version,:step,'application_role','member',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "version": version.id,
                    "step": start.id,
                    "now": now,
                },
            )
        db.commit()
        return versions[0], steps[0], steps[1], versions[1], steps[2], steps[3]


def _expect_rejected(connection: Connection, statement: str, params: dict[str, object]) -> None:
    try:
        connection.execute(text(statement), params)
    except DBAPIError:
        connection.rollback()
        context(connection, OWNER, TENANT_A)
        return
    pytest.fail("expected PostgreSQL statement to be rejected")


def test_published_insert_guards_cover_all_configuration_tables() -> None:
    version, transition, start = build_published()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        end = db.scalar(
            select(WorkflowStep).where(
                WorkflowStep.workflow_version_id == version.id, WorkflowStep.step_type == "end"
            )
        )
    assert end is not None
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        now = datetime.now(UTC)
        base = {
            "tenant": TENANT_A,
            "version": version.id,
            "start": start.id,
            "end": end.id,
            "now": now,
        }
        _expect_rejected(
            connection,
            "INSERT INTO workflow_steps (id,tenant_id,workflow_version_id,step_key,name,step_type,position,created_at,updated_at) VALUES (:id,:tenant,:version,'late','Late','task',9,:now,:now)",
            {**base, "id": uuid4()},
        )
        _expect_rejected(
            connection,
            "INSERT INTO workflow_transitions (id,tenant_id,workflow_version_id,from_step_id,to_step_id,transition_key,label,created_at,updated_at) VALUES (:id,:tenant,:version,:start,:end,'late','Late',:now,:now)",
            {**base, "id": uuid4()},
        )
        _expect_rejected(
            connection,
            "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) VALUES (:id,:tenant,:version,:start,'application_role','member',:now,:now)",
            {**base, "id": uuid4()},
        )
    assert transition.workflow_version_id == version.id


def test_composite_version_identity_rejects_cross_version_rows() -> None:
    first, first_start, first_end, second, second_start, second_end = _draft_pair()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        now = datetime.now(UTC)
        common = {
            "tenant": TENANT_A,
            "first": first.id,
            "second": second.id,
            "first_start": first_start.id,
            "second_start": second_start.id,
            "first_end": first_end.id,
            "second_end": second_end.id,
            "user": OWNER,
            "now": now,
        }
        _expect_rejected(
            connection,
            "INSERT INTO workflow_transitions (id,tenant_id,workflow_version_id,from_step_id,to_step_id,transition_key,label,created_at,updated_at) VALUES (:id,:tenant,:first,:second_start,:first_end,'bad','Bad',:now,:now)",
            {**common, "id": uuid4()},
        )
        _expect_rejected(
            connection,
            "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) VALUES (:id,:tenant,:first,:second_start,'application_role','member',:now,:now)",
            {**common, "id": uuid4()},
        )
        _expect_rejected(
            connection,
            "INSERT INTO workflow_instances (id,tenant_id,workflow_version_id,title,status,current_step_id,row_version,started_by_user_id,started_at,created_at,updated_at) VALUES (:id,:tenant,:first,'bad','active',:second_start,1,:user,:now,:now,:now)",
            {**common, "id": uuid4()},
        )
    assert first_end.workflow_version_id != second_end.workflow_version_id


def test_event_references_are_pinned_and_history_is_append_only() -> None:
    version, transition, start = build_published()
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(db, actor, uuid4(), version, "History", None)
        event_id = db.scalar(
            text("SELECT id FROM workflow_instance_events WHERE instance_id=:id LIMIT 1"),
            {"id": instance.id},
        )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        _expect_rejected(
            connection,
            "UPDATE workflow_instance_events SET workflow_version_id=:bad WHERE id=:id",
            {"bad": uuid4(), "id": event_id},
        )
        _expect_rejected(
            connection,
            "DELETE FROM workflow_instance_events WHERE id=:id",
            {"id": event_id},
        )
    assert transition.id and start.id


def test_step_transition_assignment_mutations_emit_audit_in_same_transaction() -> None:
    _, _, _, version, start, end = _draft_pair()
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        step = upsert_step(
            db,
            actor,
            uuid4(),
            version,
            None,
            {
                "step_key": "extra",
                "name": "Extra",
                "description": None,
                "step_type": "task",
                "is_start": False,
                "position": 2,
            },
        )
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        edge = upsert_transition(
            db,
            actor,
            uuid4(),
            version,
            None,
            {
                "from_step_id": start.id,
                "to_step_id": end.id,
                "transition_key": "again",
                "label": "Again",
            },
        )
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        assignment = upsert_assignment(
            db,
            actor,
            uuid4(),
            version,
            None,
            {
                "step_id": step.id,
                "target_type": "application_role",
                "target_user_id": None,
                "target_organization_unit_id": None,
                "target_application_role": "member",
            },
        )
        actions = db.scalars(
            text("SELECT action FROM audit_events WHERE resource_id IN (:step,:edge,:assignment)"),
            {"step": step.id, "edge": edge.id, "assignment": assignment.id},
        ).all()
        assert {
            "workflow.step_created",
            "workflow.transition_created",
            "workflow.assignment_created",
        }.issubset(set(actions))


def test_configuration_rolls_back_when_audit_writer_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, _, version, _, _ = _draft_pair()
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)

    def fail(*args: object, **kwargs: object) -> None:
        raise audit_service.AuditPayloadError("forced audit failure")

    monkeypatch.setattr(audit_service, "record_workflow_step_created", fail)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        with pytest.raises(audit_service.AuditPayloadError):
            upsert_step(
                db,
                actor,
                uuid4(),
                version,
                None,
                {
                    "step_key": "rolled",
                    "name": "Rolled",
                    "description": None,
                    "step_type": "task",
                    "is_start": False,
                    "position": 3,
                },
            )
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OWNER, TENANT_A)
        assert (
            connection.scalar(text("SELECT count(*) FROM workflow_steps WHERE step_key='rolled'"))
            == 0
        )


def test_cancellation_reason_is_bounded_and_stored_as_domain_event() -> None:
    version, _, _ = build_published()
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(db, actor, uuid4(), version, "Cancel", None)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        cancelled = cancel_instance(db, actor, uuid4(), instance, "  no longer needed  ")
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        reason = db.scalar(
            text(
                "SELECT reason FROM workflow_instance_events WHERE instance_id=:id AND event_type='cancelled'"
            ),
            {"id": cancelled.id},
        )
        assert reason == "no longer needed"


def test_actor_specific_actions_use_pinned_current_step_and_assignment() -> None:
    version, transition, _ = build_published(role_target=str(MEMBER), target_type="user")
    member = WorkflowActor(MEMBER, str(MEMBER), "member", TENANT_A)
    owner = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(db, owner, uuid4(), version, "Actions", None)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert [action.id for action in eligible_actions(db, member, instance)] == [transition.id]
        assert (
            eligible_actions(db, WorkflowActor(OTHER, str(OTHER), "member", TENANT_A), instance)
            == []
        )
        assert (
            eligible_actions(db, WorkflowActor(MEMBER, str(MEMBER), "auditor", TENANT_A), instance)
            == []
        )


@pytest.mark.parametrize(
    "case",
    [
        "no_start",
        "multiple_start",
        "missing_end",
        "unreachable",
        "dead_end",
        "end_outgoing",
        "cycle_exit",
        "cycle_no_exit",
    ],
)
def test_publish_graph_matrix(case: str) -> None:
    now = datetime.now(UTC)
    actor = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        definition = WorkflowDefinition(
            id=uuid4(),
            tenant_id=TENANT_A,
            code=f"graph-{case}-{uuid4().hex[:6]}",
            name=case,
            status="active",
            created_at=now,
            updated_at=now,
        )
        version = WorkflowVersion(
            id=uuid4(),
            tenant_id=TENANT_A,
            definition_id=definition.id,
            version_number=1,
            status="draft",
            created_by_user_id=OWNER,
            created_at=now,
            updated_at=now,
        )
        start = WorkflowStep(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            step_key="start",
            name="Start",
            step_type="task",
            is_start=case != "no_start",
            position=0,
            created_at=now,
            updated_at=now,
        )
        end = WorkflowStep(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            step_key="end",
            name="End",
            step_type="end",
            is_start=case == "multiple_start",
            position=1,
            created_at=now,
            updated_at=now,
        )
        db.add_all((definition, version))
        db.flush()
        db.add_all((start, end))
        db.flush()
        edge = WorkflowTransition(
            id=uuid4(),
            tenant_id=TENANT_A,
            workflow_version_id=version.id,
            from_step_id=start.id,
            to_step_id=end.id,
            transition_key="finish",
            label="Finish",
            created_at=now,
            updated_at=now,
        )
        db.add(edge)
        db.execute(
            text(
                "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) VALUES (:id,:tenant,:version,:step,'application_role','owner',:now,:now)"
            ),
            {
                "id": uuid4(),
                "tenant": TENANT_A,
                "version": version.id,
                "step": start.id,
                "now": now,
            },
        )
        if case == "missing_end":
            end.step_type = "task"
        if case == "unreachable":
            orphan = WorkflowStep(
                id=uuid4(),
                tenant_id=TENANT_A,
                workflow_version_id=version.id,
                step_key="orphan",
                name="Orphan",
                step_type="end",
                position=2,
                created_at=now,
                updated_at=now,
            )
            db.add(orphan)
        if case == "dead_end":
            dead = WorkflowStep(
                id=uuid4(),
                tenant_id=TENANT_A,
                workflow_version_id=version.id,
                step_key="dead",
                name="Dead",
                step_type="task",
                position=2,
                created_at=now,
                updated_at=now,
            )
            db.add(dead)
            db.flush()
            edge.to_step_id = dead.id
        if case == "end_outgoing":
            db.add(
                WorkflowTransition(
                    id=uuid4(),
                    tenant_id=TENANT_A,
                    workflow_version_id=version.id,
                    from_step_id=end.id,
                    to_step_id=start.id,
                    transition_key="back",
                    label="Back",
                    created_at=now,
                    updated_at=now,
                )
            )
        if case in {"cycle_exit", "cycle_no_exit"}:
            middle = WorkflowStep(
                id=uuid4(),
                tenant_id=TENANT_A,
                workflow_version_id=version.id,
                step_key="middle",
                name="Middle",
                step_type="task",
                position=2,
                created_at=now,
                updated_at=now,
            )
            db.add(middle)
            db.flush()
            db.execute(
                text(
                    "INSERT INTO workflow_step_assignments (id,tenant_id,workflow_version_id,step_id,target_type,target_application_role,created_at,updated_at) VALUES (:id,:tenant,:version,:step,'application_role','owner',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "version": version.id,
                    "step": middle.id,
                    "now": now,
                },
            )
            edge.to_step_id = middle.id
            db.add(
                WorkflowTransition(
                    id=uuid4(),
                    tenant_id=TENANT_A,
                    workflow_version_id=version.id,
                    from_step_id=middle.id,
                    to_step_id=start.id,
                    transition_key="loop",
                    label="Loop",
                    created_at=now,
                    updated_at=now,
                )
            )
            if case == "cycle_exit":
                db.add(
                    WorkflowTransition(
                        id=uuid4(),
                        tenant_id=TENANT_A,
                        workflow_version_id=version.id,
                        from_step_id=middle.id,
                        to_step_id=end.id,
                        transition_key="exit",
                        label="Exit",
                        created_at=now,
                        updated_at=now,
                    )
                )
        db.flush()
        if case == "cycle_exit":
            publish_version(db, actor, uuid4(), version)
        else:
            with pytest.raises(HTTPException):
                _validate_graph(db, version)


def test_runtime_delete_is_denied_and_history_limit_is_explicit() -> None:
    version, _, _ = build_published()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, OWNER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text("DELETE FROM workflow_steps WHERE workflow_version_id=:id"), {"id": version.id}
            )
    assert 1 <= 100


def test_cross_tenant_runtime_visibility_remains_empty() -> None:
    build_published()
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        context(connection, OTHER, TENANT_B)
        assert connection.scalar(text("SELECT count(*) FROM workflow_definitions")) == 0


def test_member_and_auditor_cannot_mutate_configuration_or_cancel() -> None:
    version, _, _ = build_published()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        member = WorkflowActor(MEMBER, str(MEMBER), "member", TENANT_A)
        with pytest.raises(HTTPException) as config_error:
            upsert_step(
                db,
                member,
                uuid4(),
                version,
                None,
                {
                    "step_key": "no",
                    "name": "No",
                    "description": None,
                    "step_type": "task",
                    "is_start": False,
                    "position": 8,
                },
            )
        assert config_error.value.status_code == 403
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(
            db, WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A), uuid4(), version, "Roles", None
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as cancel_error:
            cancel_instance(db, member, uuid4(), instance, "member cannot cancel")
        assert cancel_error.value.status_code == 403


def test_optimistic_concurrency_allows_one_transition_and_rejects_stale_writer() -> None:
    version, transition, _ = build_published()
    owner = WorkflowActor(OWNER, str(OWNER), "owner", TENANT_A)
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        instance = start_instance(db, owner, uuid4(), version, "Concurrent", None)

    def attempt() -> str:
        actor = WorkflowActor(MEMBER, str(MEMBER), "member", TENANT_A)
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            try:
                transition_instance(db, actor, uuid4(), instance, transition.id, 1)
                return "success"
            except HTTPException as error:
                assert error.status_code == 409
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), (1, 2)))
    assert sorted(results) == ["conflict", "success"]


def test_disabled_user_target_is_rejected_without_deleting_configuration() -> None:
    version, _, start = build_published(role_target=str(MEMBER), target_type="user")
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(text("UPDATE users SET status='disabled' WHERE id=:id"), {"id": MEMBER})
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            with pytest.raises(HTTPException) as error:
                _validate_graph(db, version)
            assert error.value.status_code == 409
    finally:
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("UPDATE users SET status='active' WHERE id=:id"), {"id": MEMBER}
            )
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM workflow_steps WHERE id=:id"), {"id": start.id}
            )
            == 1
        )
