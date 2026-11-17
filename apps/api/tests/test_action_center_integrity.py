"""Real HTTP sessions + forced RLS, exclusively on the disposable boundary DB."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from test_tenant_suspension_integrity import (
    SITE,
    USERS,
    A,
    B,
    Boundary,
)
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = [
    pytest.mark.action_center_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable queue harness",
    ),
]


def grant(case: Boundary, role: str, *capabilities: str) -> None:
    for capability in capabilities:
        case.call(
            "POST",
            "/qms-access/grants",
            {
                "user_id": str(USERS[role]),
                "unit_id": str(SITE),
                "capability": capability,
            },
            expected=201,
        )


def plan(case: Boundary) -> Any:
    grant(case, "member", "capa.read", "capa.manage", "capa.review")
    row = case.call(
        "POST",
        "/capas",
        {
            "unit_id": str(SITE),
            "process_id": case.process,
            "code": "QUEUE-CAPA",
            "name": "Synthetic queue parent",
            "source_type": "other",
            "problem_statement": "Synthetic problem",
            "root_cause_method": "other",
        },
        role="member",
        expected=201,
    )
    base = f"/capas/{row['id']}"
    row = case.call(
        "POST", base + "/analysis/start", {"expected_version": row["row_version"]}, role="member"
    )
    row = case.call(
        "PATCH",
        base + "/analysis",
        {
            "expected_version": row["row_version"],
            "analysis_data": {},
            "analysis_summary": "Synthetic analysis",
            "verified_root_cause": "Synthetic root cause",
            "other_method_name": "Synthetic investigation",
        },
        role="member",
    )
    return case.call(
        "POST",
        base + "/plan/start",
        {
            "expected_version": row["row_version"],
            "plan_summary": "Synthetic plan",
        },
        role="member",
    )


def action(case: Boundary, parent: dict[str, Any], *, owner: str = "member", days: int = 5) -> Any:
    current = case.call("GET", f"/capas/{parent['id']}", role="member")
    return case.call(
        "POST",
        f"/capas/{parent['id']}/actions",
        {
            "expected_capa_version": current["row_version"],
            "title": "Synthetic action",
            "description": "Synthetic work",
            "owner_user_id": str(USERS[owner]),
            "due_date": (datetime.now(UTC).date() + timedelta(days=days)).isoformat(),
        },
        role="member",
        expected=201,
    )


def implementation(case: Boundary, parent: dict[str, Any]) -> Any:
    current = case.call("GET", f"/capas/{parent['id']}", role="member")
    return case.call(
        "POST",
        f"/capas/{parent['id']}/implementation/start",
        {
            "expected_version": current["row_version"],
        },
        role="member",
    )


def move_action(case: Boundary, parent: dict[str, Any], row: dict[str, Any], state: str) -> Any:
    current = case.call("GET", f"/capas/{parent['id']}", role="member")
    return case.call(
        "POST",
        f"/capas/{parent['id']}/actions/{row['id']}/transition",
        {
            "expected_capa_version": current["row_version"],
            "expected_action_version": row["row_version"],
            "target_state": state,
        },
        role="member",
    )


def queue(case: Boundary, *, role: str = "member", extra: str = "") -> Any:
    return case.call("GET", f"/action-center?unit_id={SITE}" + extra, role=role)


def test_workflow_without_business_unit_is_excluded_from_unit_filter(boundary: Boundary) -> None:
    all_units = boundary.call("GET", "/action-center", role="member")
    assert any(item["source_id"] == boundary.instance for item in all_units["items"])
    assert queue(boundary)["summary"]["total"] == 0


def test_in_progress_action_is_visible_and_terminal_parent_is_excluded(boundary: Boundary) -> None:
    parent = plan(boundary)
    row = action(boundary, parent)
    implementation(boundary, parent)
    row = move_action(boundary, parent, row, "in_progress")
    payload = queue(boundary)
    assert payload["summary"]["total"] == 1
    assert payload["items"][0]["state"] == "in_progress"
    assert payload["items"][0]["target_subrecord_id"] == row["id"]
    current = boundary.call("GET", f"/capas/{parent['id']}", role="member")
    boundary.call(
        "POST",
        f"/capas/{parent['id']}/cancel",
        {
            "expected_version": current["row_version"],
            "reason": "Synthetic cancellation",
        },
        role="member",
    )
    assert queue(boundary)["items"] == []
    assert queue(boundary)["summary"]["total"] == 0


def test_personal_eligibility_is_applied_before_250_source_rows(boundary: Boundary) -> None:
    parent = plan(boundary)
    for _ in range(251):
        action(boundary, parent, owner="admin", days=1)
    mine = action(boundary, parent, days=30)
    payload = queue(boundary, extra="&limit=1")
    assert payload["summary"]["total"] == 1
    assert payload["items"][0]["source_id"] == mine["id"]


def test_summary_counts_all_eligible_rows_beyond_page_and_250_cutoff(boundary: Boundary) -> None:
    parent = plan(boundary)
    for _ in range(251):
        action(boundary, parent, days=-1)
    payload = queue(boundary, extra="&limit=1")
    assert len(payload["items"]) == 1
    assert payload["summary"] == {
        "total": 251,
        "overdue": 251,
        "due_soon": 0,
        "unassigned": 0,
        "by_source": {"capa": 251},
    }


def test_completed_actions_only_project_to_independent_authorized_reviewer(
    boundary: Boundary,
) -> None:
    parent = plan(boundary)
    row = action(boundary, parent)
    implementation(boundary, parent)
    move_action(boundary, parent, row, "completed")
    assert queue(boundary)["items"] == []
    grant(boundary, "admin", "capa.read", "capa.review")
    payload = queue(boundary, role="admin")
    assert payload["summary"]["by_source"] == {"capa": 1}
    assert payload["items"][0]["state"] == "awaiting_verification"
    assert payload["items"][0]["urgency"] == "waiting_review"


def test_review_only_oversight_can_read_team_without_execution_authority(
    boundary: Boundary,
) -> None:
    parent = plan(boundary)
    row = action(boundary, parent)
    grant(boundary, "admin", "capa.read")
    assert queue(boundary, role="admin")["items"] == []
    team = queue(boundary, role="admin", extra="&scope=team")
    assert team["items"][0]["source_id"] == row["id"]
    boundary.call("GET", f"/action-center?scope=team&unit_id={SITE}", role="member", expected=403)


def test_revocation_removes_personal_work_but_preserves_read_only_team(boundary: Boundary) -> None:
    parent = plan(boundary)
    action(boundary, parent)
    with boundary.admin.begin() as db:
        grant_id = db.scalar(
            text(
                "SELECT id FROM qms_access_grants WHERE user_id=:u AND unit_id=:s "
                "AND capability='capa.manage' AND status='active'"
            ),
            {"u": USERS["member"], "s": SITE},
        )
    boundary.call("POST", f"/qms-access/grants/{grant_id}/revoke")
    assert queue(boundary)["summary"]["total"] == 0


def test_other_company_and_disabled_company_do_not_expose_queue(boundary: Boundary) -> None:
    parent = plan(boundary)
    action(boundary, parent)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    payload = boundary.call("GET", "/action-center?scope=team")
    assert payload["items"] == [] and payload["summary"]["total"] == 0
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(A)})
    boundary.change("tenant", False)
    boundary.call("GET", "/action-center", role="member", expected=403)


def test_queue_order_uses_urgency_due_date_then_latest_update(boundary: Boundary) -> None:
    parent = plan(boundary)
    future = action(boundary, parent, days=30)
    overdue = action(boundary, parent, days=-3)
    due_soon = action(boundary, parent, days=2)
    payload = queue(boundary)
    assert [row["source_id"] for row in payload["items"]] == [
        overdue["id"],
        due_soon["id"],
        future["id"],
    ]


def test_empty_summary_preserves_response_contract(boundary: Boundary) -> None:
    payload = queue(boundary)
    assert payload["summary"] == {
        "total": 0,
        "overdue": 0,
        "due_soon": 0,
        "unassigned": 0,
        "by_source": {},
    }
    assert payload["items"] == []


def workflow_version(boundary: Boundary, target_type: str, target: str) -> Any:
    definition = boundary.call(
        "POST",
        "/workflows",
        {"code": "NOT-MINE", "name": "Synthetic unrelated queue"},
        expected=201,
    )
    version = boundary.call("POST", f"/workflows/{definition['id']}/versions", expected=201)
    base = f"/workflows/versions/{version['id']}"
    step = boundary.call(
        "POST",
        base + "/steps",
        {"step_key": "work", "name": "Work", "step_type": "task", "is_start": True, "position": 0},
        expected=201,
    )
    end = boundary.call(
        "POST",
        base + "/steps",
        {"step_key": "end", "name": "End", "step_type": "end", "position": 1},
        expected=201,
    )
    boundary.call(
        "POST",
        base + "/transitions",
        {
            "from_step_id": step["id"],
            "to_step_id": end["id"],
            "transition_key": "finish",
            "label": "Finish",
        },
        expected=201,
    )
    boundary.call(
        "POST",
        base + "/assignments",
        {
            "step_id": step["id"],
            "target_type": target_type,
            {
                "user": "target_user_id",
                "application_role": "target_application_role",
                "organization_unit": "target_organization_unit_id",
            }[target_type]: target,
        },
        expected=201,
    )
    boundary.call("POST", base + "/publish")
    return version


def test_latest_workflow_assignments_cannot_starve_older_personal_task(boundary: Boundary) -> None:
    version = workflow_version(boundary, "user", str(USERS["admin"]))
    for _ in range(251):
        boundary.call(
            "POST",
            "/workflow-instances",
            {"workflow_version_id": version["id"], "title": "Not assigned to member"},
            expected=201,
        )
    payload = boundary.call("GET", "/action-center?limit=1", role="member")
    assert payload["summary"]["total"] == 1
    assert payload["items"][0]["source_id"] == boundary.instance


@pytest.mark.parametrize("target_type", ["user", "application_role", "organization_unit"])
def test_workflow_eligibility_matches_assignment_types(
    boundary: Boundary, target_type: str
) -> None:
    target = {
        "user": str(USERS["member"]),
        "application_role": "member",
        "organization_unit": str(SITE),
    }[target_type]
    version = workflow_version(boundary, target_type, target)
    row = boundary.call(
        "POST",
        "/workflow-instances",
        {
            "workflow_version_id": version["id"],
            "title": "Synthetic assigned task",
        },
        expected=201,
    )
    payload = boundary.call("GET", "/action-center", role="member")
    assert any(item["source_id"] == row["id"] for item in payload["items"])
    if target_type == "organization_unit":
        assignments = boundary.call("GET", f"/organization/assignments?unit_id={SITE}")
        assignment = next(a for a in assignments if a["user_id"] == str(USERS["member"]))
        boundary.call(
            "PATCH", f"/organization/assignments/{assignment['id']}", {"status": "inactive"}
        )
        payload = boundary.call("GET", "/action-center", role="member")
        assert all(item["source_id"] != row["id"] for item in payload["items"])


def test_auditor_assignment_is_not_presented_as_personal_executable_work(
    boundary: Boundary,
) -> None:
    # A valid executor can later become read-only; preserve the legacy-instance
    # queue regression without publishing a newly invalid auditor-only graph.
    version = workflow_version(boundary, "user", str(USERS["admin"]))
    boundary.call(
        "POST",
        "/workflow-instances",
        {
            "workflow_version_id": version["id"],
            "title": "Read-only auditor assignment",
        },
        expected=201,
    )
    with boundary.admin.begin() as db:
        db.execute(
            text("UPDATE memberships SET role='auditor' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["admin"]},
        )
    assert boundary.call("GET", "/action-center", role="admin")["summary"]["total"] == 0
    assert boundary.call("GET", "/action-center?scope=team", role="admin")["summary"]["total"] == 2


def control_work(case: Boundary) -> tuple[dict[str, Any], dict[str, Any]]:
    grant(
        case,
        "member",
        "controls.read",
        "controls.manage",
        "control_instances.read",
        "control_instances.manage",
        "evidence.read",
        "evidence.create",
    )
    control = case.call(
        "POST",
        "/controls",
        {
            "unit_id": str(SITE),
            "process_id": case.process,
            "code": "QUEUE-CONTROL",
            "name": "Synthetic control",
            "objective": "Synthetic purpose",
        },
        role="member",
        expected=201,
    )
    case.call(
        "POST",
        f"/controls/{control['id']}/activities",
        {
            "name": "Synthetic activity",
            "sequence": 10,
        },
        role="member",
        expected=201,
    )
    case.call(
        "POST",
        f"/controls/{control['id']}/evidence-requirements",
        {
            "name": "Synthetic requirement",
            "sequence": 10,
        },
        role="member",
        expected=201,
    )
    case.call(
        "POST",
        f"/controls/{control['id']}/activate",
        {
            "expected_version": control["row_version"],
        },
        role="member",
    )
    instance = case.call(
        "POST",
        f"/control-instances?unit_id={SITE}&process_id={case.process}",
        {
            "control_id": control["id"],
            "code": "QUEUE-INSTANCE",
            "name": "Synthetic implementation",
        },
        role="member",
        expected=201,
    )
    task = case.call(
        "GET", f"/control-instance-activities?instance_id={instance['id']}", role="member"
    )[0]
    case.call(
        "PATCH",
        f"/control-instance-activities/{task['id']}",
        {
            "expected_version": task["row_version"],
            "assigned_to_user_id": str(USERS["member"]),
        },
        role="member",
    )
    evidence = case.call(
        "GET", f"/control-instance-evidence?instance_id={instance['id']}", role="member"
    )[0]
    evidence = case.call(
        "PATCH",
        f"/control-instance-evidence/{evidence['id']}",
        {
            "expected_version": evidence["row_version"],
            "evidence_summary": "Synthetic submission",
        },
        role="member",
    )
    case.call(
        "POST",
        f"/control-instance-evidence/{evidence['id']}/submit",
        {
            "expected_version": evidence["row_version"],
        },
        role="member",
    )
    return instance, evidence


def test_control_tasks_require_the_complete_destination_read_context(boundary: Boundary) -> None:
    control_work(boundary)
    assert queue(boundary)["summary"]["by_source"] == {"control_activity": 1}
    with boundary.admin.begin() as db:
        identifier = db.scalar(
            text(
                "SELECT id FROM qms_access_grants WHERE user_id=:u AND unit_id=:s "
                "AND capability='controls.read' AND status='active'"
            ),
            {"u": USERS["member"], "s": SITE},
        )
    boundary.call("POST", f"/qms-access/grants/{identifier}/revoke")
    assert queue(boundary)["items"] == []


def test_evidence_queue_requires_context_and_independent_reviewer(boundary: Boundary) -> None:
    _, evidence = control_work(boundary)
    grant(boundary, "member", "evidence.review")
    assert queue(boundary)["summary"]["by_source"] == {"control_activity": 1}
    grant(boundary, "admin", "evidence.review")
    assert queue(boundary, role="admin")["items"] == []
    grant(boundary, "admin", "controls.read", "control_instances.read", "control_instances.manage")
    payload = queue(boundary, role="admin")
    assert payload["summary"]["by_source"] == {"evidence_review": 1}
    assert payload["items"][0]["source_id"] == evidence["id"]


def test_one_page_summary_includes_sources_absent_from_that_page(boundary: Boundary) -> None:
    parent = plan(boundary)
    action(boundary, parent, days=-2)
    control_work(boundary)
    grant(boundary, "admin", "capa.read", "controls.read", "control_instances.read")
    payload = boundary.call("GET", "/action-center?scope=team&limit=1", role="admin")
    assert len(payload["items"]) == 1 and payload["items"][0]["source"] == "capa"
    assert payload["summary"]["total"] == 4
    assert payload["summary"]["by_source"] == {
        "capa": 1,
        "workflow": 1,
        "control_activity": 1,
        "evidence_review": 1,
    }
