"""Executor readiness through real HTTP/RLS, on a strictly disposable database."""

from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import text
from test_tenant_suspension_integrity import SITE, USERS, A, Boundary
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = [
    pytest.mark.workflow_executor_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable executor harness",
    ),
]


def draft(case: Boundary, target_type: str, target: str, *, future_step: bool = False) -> Any:
    definition = case.call(
        "POST",
        "/workflows",
        {
            "code": "EXECUTOR",
            "name": "Synthetic executor validation",
        },
        expected=201,
    )
    version = case.call("POST", f"/workflows/{definition['id']}/versions", expected=201)
    base = f"/workflows/versions/{version['id']}"
    start = case.call(
        "POST",
        base + "/steps",
        {
            "step_key": "start",
            "name": "Start",
            "step_type": "task",
            "is_start": True,
            "position": 0,
        },
        expected=201,
    )
    end = case.call(
        "POST",
        base + "/steps",
        {
            "step_key": "end",
            "name": "End",
            "step_type": "end",
            "position": 2,
        },
        expected=201,
    )
    work = start
    if future_step:
        work = case.call(
            "POST",
            base + "/steps",
            {
                "step_key": "later",
                "name": "Later",
                "step_type": "approval",
                "position": 1,
            },
            expected=201,
        )
        case.call(
            "POST",
            base + "/transitions",
            {
                "from_step_id": start["id"],
                "to_step_id": work["id"],
                "transition_key": "next",
                "label": "Next",
            },
            expected=201,
        )
        case.call(
            "POST",
            base + "/assignments",
            {
                "step_id": start["id"],
                "target_type": "user",
                "target_user_id": str(USERS["owner"]),
            },
            expected=201,
        )
    case.call(
        "POST",
        base + "/transitions",
        {
            "from_step_id": work["id"],
            "to_step_id": end["id"],
            "transition_key": "finish",
            "label": "Finish",
        },
        expected=201,
    )
    field = {
        "user": "target_user_id",
        "application_role": "target_application_role",
        "organization_unit": "target_organization_unit_id",
    }[target_type]
    case.call(
        "POST",
        base + "/assignments",
        {
            "step_id": work["id"],
            "target_type": target_type,
            field: target,
        },
        expected=201,
    )
    return {"version": version, "definition": definition, "base": base}


def counts(case: Boundary) -> tuple[int, int, int]:
    with case.admin.connect() as db:
        row = db.execute(
            text(
                "SELECT (SELECT count(*) FROM workflow_instances), "
                "(SELECT count(*) FROM workflow_instance_events), "
                "(SELECT count(*) FROM audit_events)"
            )
        ).one()
        return int(row[0]), int(row[1]), int(row[2])


def start(case: Boundary, version: str, *, expected: int = 201) -> Any:
    return case.call(
        "POST",
        "/workflow-instances",
        {
            "workflow_version_id": version,
            "title": "Synthetic new instance",
        },
        expected=expected,
    )


def change_member(case: Boundary, change: str) -> None:
    with case.admin.begin() as db:
        if change == "role":
            db.execute(
                text("UPDATE memberships SET role='auditor' WHERE tenant_id=:t AND user_id=:u"),
                {"t": A, "u": USERS["member"]},
            )
        elif change == "user":
            db.execute(
                text("UPDATE users SET status='disabled' WHERE id=:u"), {"u": USERS["member"]}
            )
        elif change == "membership":
            db.execute(
                text("UPDATE memberships SET status='revoked' WHERE tenant_id=:t AND user_id=:u"),
                {"t": A, "u": USERS["member"]},
            )
        elif change == "assignment":
            db.execute(
                text(
                    "UPDATE organization_unit_assignments SET status='inactive' "
                    "WHERE tenant_id=:t AND unit_id=:s AND user_id=:u"
                ),
                {"t": A, "s": SITE, "u": USERS["member"]},
            )


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_publish_and_start_with_executable_direct_user(boundary: Boundary, role: str) -> None:
    graph = draft(boundary, "user", str(USERS[role]))
    boundary.call("POST", graph["base"] + "/publish")
    assert start(boundary, graph["version"]["id"])["status"] == "active"


def test_auditor_only_assignment_cannot_publish_and_draft_history_survives(
    boundary: Boundary,
) -> None:
    graph = draft(boundary, "user", str(USERS["auditor"]))
    before = counts(boundary)
    boundary.call("POST", graph["base"] + "/publish", expected=409)
    assert boundary.call("GET", graph["base"])["status"] == "draft"
    assert len(boundary.call("GET", graph["base"] + "/assignments")) == 1
    assert counts(boundary) == before


@pytest.mark.parametrize("target_type", ["user", "application_role", "organization_unit"])
@pytest.mark.parametrize("change", ["role", "user", "membership"])
def test_publish_requires_an_active_executor(
    boundary: Boundary, target_type: str, change: str
) -> None:
    target = {
        "user": str(USERS["member"]),
        "application_role": "member",
        "organization_unit": str(SITE),
    }[target_type]
    graph = draft(boundary, target_type, target)
    change_member(boundary, change)
    before = counts(boundary)
    boundary.call("POST", graph["base"] + "/publish", expected=409)
    assert counts(boundary) == before


@pytest.mark.parametrize("target_type", ["user", "application_role", "organization_unit"])
@pytest.mark.parametrize("change", ["role", "user", "membership"])
def test_start_revalidates_published_executor_without_creating_partial_history(
    boundary: Boundary,
    target_type: str,
    change: str,
) -> None:
    target = {
        "user": str(USERS["member"]),
        "application_role": "member",
        "organization_unit": str(SITE),
    }[target_type]
    graph = draft(boundary, target_type, target)
    boundary.call("POST", graph["base"] + "/publish")
    change_member(boundary, change)
    before = counts(boundary)
    start(boundary, graph["version"]["id"], expected=409)
    assert counts(boundary) == before
    assert boundary.call("GET", graph["base"])["status"] == "published"


def test_unit_requires_active_assignment_even_when_member_is_active(boundary: Boundary) -> None:
    graph = draft(boundary, "organization_unit", str(SITE))
    change_member(boundary, "assignment")
    boundary.call("POST", graph["base"] + "/publish", expected=409)


def test_published_unit_losing_assignment_cannot_start(boundary: Boundary) -> None:
    graph = draft(boundary, "organization_unit", str(SITE))
    boundary.call("POST", graph["base"] + "/publish")
    change_member(boundary, "assignment")
    before = counts(boundary)
    start(boundary, graph["version"]["id"], expected=409)
    assert counts(boundary) == before


def test_all_future_steps_are_validated_when_starting(boundary: Boundary) -> None:
    graph = draft(boundary, "user", str(USERS["member"]), future_step=True)
    boundary.call("POST", graph["base"] + "/publish")
    change_member(boundary, "role")
    before = counts(boundary)
    start(boundary, graph["version"]["id"], expected=409)
    assert counts(boundary) == before


def test_retired_definition_cannot_start_but_existing_work_can_finish(boundary: Boundary) -> None:
    boundary.call("PATCH", f"/workflows/{boundary.definition}", {"status": "retired"})
    before = counts(boundary)
    start(boundary, boundary.version, expected=409)
    assert counts(boundary) == before
    actions = boundary.call(
        "GET", f"/workflow-instances/{boundary.instance}/actions", role="member"
    )
    result = boundary.call(
        "POST",
        f"/workflow-instances/{boundary.instance}/transition",
        {
            "transition_id": actions[0]["id"],
            "expected_version": 1,
        },
        role="member",
    )
    assert result["status"] == "completed"


def test_restoring_eligible_people_does_not_rewrite_published_version(boundary: Boundary) -> None:
    graph = draft(boundary, "user", str(USERS["member"]))
    published = boundary.call("POST", graph["base"] + "/publish")
    change_member(boundary, "role")
    start(boundary, graph["version"]["id"], expected=409)
    with boundary.admin.begin() as db:
        db.execute(
            text("UPDATE memberships SET role='member' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["member"]},
        )
    assert start(boundary, graph["version"]["id"])["status"] == "active"
    assert boundary.call("GET", graph["base"]) == published


def test_empty_unit_is_a_draft_target_but_not_a_publishable_executor(boundary: Boundary) -> None:
    unit = boundary.call(
        "POST",
        "/organization/units",
        {
            "code": "EMPTY",
            "name": "Synthetic empty team",
            "unit_type": "team",
        },
        expected=201,
    )
    graph = draft(boundary, "organization_unit", unit["id"])
    boundary.call("POST", graph["base"] + "/publish", expected=409)


def test_mixed_unit_can_publish_when_at_least_one_member_can_execute(boundary: Boundary) -> None:
    boundary.call(
        "POST",
        "/organization/assignments",
        {
            "unit_id": str(SITE),
            "user_id": str(USERS["auditor"]),
            "assignment_role": "member",
        },
        expected=201,
    )
    graph = draft(boundary, "organization_unit", str(SITE))
    assert boundary.call("POST", graph["base"] + "/publish")["status"] == "published"
    assert start(boundary, graph["version"]["id"])["status"] == "active"


def test_transition_does_not_orphan_work_at_a_destination_without_executors(
    boundary: Boundary,
) -> None:
    graph = draft(boundary, "user", str(USERS["member"]), future_step=True)
    boundary.call("POST", graph["base"] + "/publish")
    instance = start(boundary, graph["version"]["id"])
    actions = boundary.call("GET", f"/workflow-instances/{instance['id']}/actions")
    change_member(boundary, "role")
    before = counts(boundary)
    boundary.call(
        "POST",
        f"/workflow-instances/{instance['id']}/transition",
        {
            "expected_version": instance["row_version"],
            "transition_id": actions[0]["id"],
        },
        expected=409,
    )
    assert counts(boundary) == before
    assert boundary.call("GET", f"/workflow-instances/{instance['id']}")["row_version"] == 1


def test_terminal_start_cannot_publish_an_unfinishable_active_instance(boundary: Boundary) -> None:
    definition = boundary.call(
        "POST",
        "/workflows",
        {
            "code": "END-ONLY",
            "name": "Synthetic terminal start",
        },
        expected=201,
    )
    version = boundary.call("POST", f"/workflows/{definition['id']}/versions", expected=201)
    base = f"/workflows/versions/{version['id']}"
    boundary.call(
        "POST",
        base + "/steps",
        {
            "step_key": "end",
            "name": "End",
            "step_type": "end",
            "is_start": True,
            "position": 0,
        },
        expected=201,
    )
    before = counts(boundary)
    boundary.call("POST", base + "/publish", expected=409)
    assert counts(boundary) == before
    assert boundary.call("GET", base)["status"] == "draft"


def test_retired_definition_cannot_publish_a_new_version(boundary: Boundary) -> None:
    graph = draft(boundary, "user", str(USERS["member"]))
    boundary.call("PATCH", f"/workflows/{graph['definition']['id']}", {"status": "retired"})
    before = counts(boundary)
    boundary.call("POST", graph["base"] + "/publish", expected=409)
    assert counts(boundary) == before
    assert boundary.call("GET", graph["base"])["status"] == "draft"
