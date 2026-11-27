# ruff: noqa: E501, S608 -- statements interpolate only constant test allowlists.
"""Real HTTP/session/CSRF/RLS boundaries in a disposable PostgreSQL fixture."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, A, B, Boundary, context, sqlstate
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires dedicated disposable PostgreSQL; never customer data",
)


def grant(
    case: Boundary, role: str = "member", unit: str = str(SITE), *, manage: bool = True
) -> None:
    for cap in ("projects.read", "projects.manage") if manage else ("projects.read",):
        case.call(
            "POST",
            "/qms-access/grants",
            {"user_id": str(USERS[role]), "unit_id": unit, "capability": cap},
            expected=201,
        )


def create(
    case: Boundary, *, code: str = "PLAN-001", journey: str = "initial", unit: str = str(SITE)
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        case.call(
            "POST",
            "/qms-projects",
            {"unit_id": unit, "code": code, "name": "Synthetic project", "journey_key": journey},
            role="member",
            expected=201,
        ),
    )


def step_patch(project: dict[str, Any], step: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "expected_project_version": project["row_version"],
        "expected_version": step["row_version"],
        **changes,
    }


def test_http_project_create_all_frozen_steps_and_explicit_authority(boundary: Boundary) -> None:
    body = {
        "unit_id": str(SITE),
        "code": "PLAN-001",
        "name": "Synthetic project",
        "journey_key": "initial",
    }
    boundary.call("POST", "/qms-projects", body, expected=403)  # Owner has no implicit authority.
    grant(boundary, manage=False)
    boundary.call("POST", "/qms-projects", body, role="member", expected=403)
    boundary.call(
        "POST",
        "/qms-access/grants",
        {"user_id": str(USERS["member"]), "unit_id": str(SITE), "capability": "projects.manage"},
        expected=201,
    )
    project = create(boundary)
    assert project["tenant_id"] == str(A) and project["unit_id"] == str(SITE)
    assert project["catalog_version"] == "guided-qms-v1" and project["row_version"] == 1
    assert [(s["step_key"], s["position"], s["status"]) for s in project["steps"]] == [
        ("process-map", 1, "not_started"),
        ("normative-profile", 2, "feature_pending"),
        ("document-control", 3, "not_started"),
        ("control-implementation", 4, "not_started"),
        ("risk-response", 5, "not_started"),
        ("people-and-performance", 6, "feature_pending"),
        ("audit-plan", 7, "not_started"),
        ("management-review", 8, "feature_pending"),
    ]
    assert all(s["project_id"] == project["id"] and s["row_version"] == 1 for s in project["steps"])
    assert boundary.call("GET", f"/qms-projects/{project['id']}", role="member") == project
    assert (
        boundary.call("GET", f"/qms-projects?unit_id={SITE}", role="member")[0]["id"]
        == project["id"]
    )
    boundary.call(
        "POST", "/qms-projects", {**body, "code": "plan-001"}, role="member", expected=409
    )
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_access_grants WHERE capability LIKE 'projects.%'")
            )
            == 2
        )
        assert (
            db.scalar(text("SELECT count(*) FROM audit_events WHERE action='qms_project.created'"))
            == 1
        )


def test_step_planning_notes_feature_pending_and_parent_versions(boundary: Boundary) -> None:
    grant(boundary)
    p = create(boundary)
    step, gap = p["steps"][:2]
    path = f"/qms-projects/{p['id']}/steps/{step['id']}"
    boundary.call(
        "PATCH",
        path,
        step_patch(p, step, status="reported", notes=" \n "),
        role="member",
        expected=422,
    )
    p2 = boundary.call(
        "PATCH",
        path,
        step_patch(
            p,
            step,
            status="reported",
            notes="Self reported; verification pending",
            assignee_user_id=str(USERS["admin"]),
        ),
        role="member",
    )
    assert p2["row_version"] == 2 and p2["steps"][0]["row_version"] == 2
    assert p2["steps"][0]["status"] == "reported"
    assert p2["steps"][0]["assignee_user_id"] == str(
        USERS["admin"]
    )  # Active member without unit assignment.
    boundary.call(
        "PATCH", path, step_patch(p, step, notes="Stale draft"), role="member", expected=409
    )
    boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}/steps/{gap['id']}",
        step_patch(p2, gap, status="reported", notes="Cannot manufacture completion"),
        role="member",
        expected=422,
    )
    p3 = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}/steps/{gap['id']}",
        step_patch(
            p2, gap, notes="Waiting for reviewed product capability", target_date="2027-02-01"
        ),
        role="member",
    )
    assert p3["row_version"] == 3 and p3["steps"][1]["status"] == "feature_pending"
    boundary.call(
        "PATCH", path, step_patch(p3, p3["steps"][0], notes=""), role="member", expected=422
    )


def test_cross_company_unit_hidden_rows_and_auditor_read_only(boundary: Boundary) -> None:
    grant(boundary)
    p = create(boundary)
    boundary.call("GET", f"/qms-projects/{p['id']}", role="admin", expected=404)
    boundary.call("GET", f"/qms-projects?unit_id={B_SITE}", role="member", expected=403)
    boundary.call(
        "POST",
        "/qms-projects",
        {
            "unit_id": str(B_SITE),
            "code": "CROSS",
            "name": "Denied",
            "journey_key": "initial",
            "tenant_id": str(B),
        },
        role="member",
        expected=422,
    )
    grant(boundary, "auditor", manage=False)
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="auditor")["id"] == p["id"]
    boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}",
        {"expected_version": 1, "name": "Denied"},
        role="auditor",
        expected=403,
    )
    boundary.call(
        "POST",
        "/qms-access/grants",
        {"user_id": str(USERS["auditor"]), "unit_id": str(SITE), "capability": "projects.manage"},
        expected=409,
    )
    with boundary.runtime.begin() as db:
        context(db, USERS["member"], B)
        assert db.scalar(text("SELECT count(*) FROM qms_projects")) == 0
        assert db.scalar(text("SELECT count(*) FROM qms_project_steps")) == 0


def test_archive_restore_and_audit_failure_rollback(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant(boundary)
    p = create(boundary)
    path = f"/qms-projects/{p['id']}"
    boundary.call(
        "POST",
        path + "/status",
        {"expected_version": 1, "target_status": "archived", "reason": "   "},
        role="member",
        expected=422,
    )
    archived = boundary.call(
        "POST",
        path + "/status",
        {"expected_version": 1, "target_status": "archived", "reason": "Paused planning"},
        role="member",
    )
    assert archived["row_version"] == 2 and archived["status"] == "archived"
    boundary.call(
        "PATCH", path, {"expected_version": 2, "name": "Cannot edit"}, role="member", expected=409
    )
    boundary.call(
        "PATCH",
        path + f"/steps/{p['steps'][0]['id']}",
        step_patch(archived, p["steps"][0], notes="Cannot edit"),
        role="member",
        expected=409,
    )
    restored = boundary.call(
        "POST",
        path + "/status",
        {"expected_version": 2, "target_status": "open", "reason": "Resume planning"},
        role="member",
    )
    assert restored["row_version"] == 3

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(audit_service, "record_qms_project", fail)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        boundary.call(
            "PATCH", path, {"expected_version": 3, "name": "Must rollback"}, role="member"
        )
    assert boundary.call("GET", path, role="member") == restored
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        create(boundary, code="ROLLBACK")
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM qms_projects WHERE code='ROLLBACK'")) == 0
        assert (
            db.scalar(text("SELECT count(*) FROM audit_events WHERE action LIKE 'qms_project.%'"))
            == 3
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("row_version", 3),
        ("unit_id", str(B_SITE)),
        ("code", "FORGED"),
        ("catalog_version", "future"),
        ("created_by_user_id", str(USERS["admin"])),
    ],
)
def test_direct_sql_project_identity_and_version_guards(
    boundary: Boundary, field: str, value: Any
) -> None:
    grant(boundary)
    p = create(boundary)
    with pytest.raises(DBAPIError), boundary.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                f"UPDATE qms_projects SET {field}=:value,updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": p["id"], "value": value},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE qms_project_steps SET status='reported',notes='',row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id",
        "UPDATE qms_project_steps SET step_key='forged',row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id",
        "UPDATE qms_project_steps SET position=99,row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id",
        "UPDATE qms_project_steps SET notes='forged no parent increment',row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id",
        "DELETE FROM qms_project_steps WHERE id=:id",
    ],
)
def test_direct_sql_step_catalog_parent_and_delete_guards(
    boundary: Boundary, statement: str
) -> None:
    grant(boundary)
    p = create(boundary)
    with pytest.raises(DBAPIError), boundary.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(text(statement), {"id": p["steps"][0]["id"]})


def test_concurrent_metadata_and_step_reject_stale_parent_without_partial_write(
    boundary: Boundary,
) -> None:
    grant(boundary)
    p = create(boundary)

    def metadata() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .patch(
                f"/qms-projects/{p['id']}",
                json={"expected_version": 1, "name": "Concurrent metadata"},
            )
            .status_code,
        )

    def step() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .patch(
                f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
                json=step_patch(p, p["steps"][0], notes="Concurrent step"),
            )
            .status_code,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(metadata), pool.submit(step)]
        assert sorted(f.result(timeout=10) for f in futures) == [200, 409]
    final = boundary.call("GET", f"/qms-projects/{p['id']}", role="member")
    assert final["row_version"] == 2
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action IN ('qms_project.updated','qms_project_step.updated')"
                )
            )
            == 1
        )


def test_project_scope_blocks_unit_archive_and_preserves_inactive_assignment_history(
    boundary: Boundary,
) -> None:
    grant(boundary)
    p = create(boundary)
    p = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}",
        {"expected_version": 1, "coordinator_user_id": str(USERS["admin"])},
        role="member",
    )
    with boundary.admin.begin() as db:
        db.execute(
            text("UPDATE memberships SET status='revoked' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["admin"]},
        )
    p = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}",
        {"expected_version": 2, "name": "Preserve historical coordinator"},
        role="member",
    )
    assert p["coordinator_user_id"] == str(USERS["admin"])
    boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
        step_patch(p, p["steps"][0], assignee_user_id=str(USERS["admin"])),
        role="member",
        expected=409,
    )
    with boundary.admin.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text("UPDATE organization_unit_assignments SET status='inactive' WHERE unit_id=:id"),
            {"id": SITE},
        )
        db.execute(
            text(
                "UPDATE qms_processes SET status='archived',row_version=row_version+1,updated_at=clock_timestamp() WHERE unit_id=:id"
            ),
            {"id": SITE},
        )
    with pytest.raises(DBAPIError), boundary.runtime.begin() as db:
        context(db)
        db.execute(
            text(
                "UPDATE organization_units SET status='archived',updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": SITE},
        )


@pytest.mark.parametrize(
    "journey,count,gaps",
    [
        ("initial", 8, 3),
        ("improve", 7, 2),
        ("transition", 8, 4),
        ("migrate", 6, 3),
        ("audit", 8, 2),
        ("expand", 7, 2),
    ],
)
def test_each_journey_generates_complete_server_catalog(
    boundary: Boundary, journey: str, count: int, gaps: int
) -> None:
    grant(boundary)
    p = create(boundary, journey=journey)
    assert len(p["steps"]) == count
    assert sum(s["status"] == "feature_pending" for s in p["steps"]) == gaps
    assert [s["position"] for s in p["steps"]] == list(range(1, count + 1))
    assert set(p) == {
        "id",
        "tenant_id",
        "unit_id",
        "code",
        "name",
        "journey_key",
        "catalog_version",
        "scope_summary",
        "coordinator_user_id",
        "target_date",
        "status",
        "row_version",
        "created_by_user_id",
        "created_at",
        "updated_at",
        "steps",
    }
    assert set(p["steps"][0]) == {
        "id",
        "tenant_id",
        "unit_id",
        "project_id",
        "step_key",
        "position",
        "status",
        "notes",
        "assignee_user_id",
        "target_date",
        "row_version",
        "updated_by_user_id",
        "updated_at",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"expected_version": True, "name": "Bad version"},
        {"expected_version": "1", "name": "Bad version"},
        {"expected_version": 1},
        {"expected_version": 1, "scope_summary": None},
        {"expected_version": 1, "name": None},
        {"expected_version": 1, "journey_key": "audit"},
        {"expected_version": 1, "code": "FORGED"},
    ],
)
def test_project_patch_rejects_invalid_or_immutable_fields(
    boundary: Boundary, body: dict[str, Any]
) -> None:
    grant(boundary)
    p = create(boundary)
    boundary.call("PATCH", f"/qms-projects/{p['id']}", body, role="member", expected=422)


def test_revoked_manage_and_assignment_never_grant_unit_access(boundary: Boundary) -> None:
    grant(boundary)
    p = create(boundary)
    p = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}",
        {"expected_version": 1, "coordinator_user_id": str(USERS["admin"])},
        role="member",
    )
    boundary.call("GET", f"/qms-projects/{p['id']}", role="admin", expected=404)
    rows = boundary.call("GET", "/qms-access/grants")
    manage = next(
        g
        for g in rows
        if g["user_id"] == str(USERS["member"]) and g["capability"] == "projects.manage"
    )
    boundary.call("POST", f"/qms-access/grants/{manage['id']}/revoke")
    boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}",
        {"expected_version": 2, "name": "Denied"},
        role="member",
        expected=403,
    )
    assert (
        boundary.call("GET", f"/qms-projects/{p['id']}", role="member")["name"]
        == "Synthetic project"
    )
    with boundary.runtime.begin() as db:
        context(db, USERS["member"])
        assert (
            db.execute(
                text(
                    "UPDATE qms_projects SET name='Denied',row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": p["id"]},
            ).rowcount
            == 0
        )


@pytest.mark.parametrize("subject", ["tenant", "user", "membership"])
def test_inactive_actor_or_company_denies_raw_sql_reads(boundary: Boundary, subject: str) -> None:
    grant(boundary)
    p = create(boundary)
    sql = {
        "tenant": ("UPDATE tenants SET status='disabled' WHERE id=:id", A),
        "user": ("UPDATE users SET status='disabled' WHERE id=:id", USERS["member"]),
        "membership": (
            "UPDATE memberships SET status='revoked' WHERE tenant_id=:id AND user_id=:u",
            A,
        ),
    }
    statement, identifier = sql[subject]
    with boundary.admin.begin() as db:
        db.execute(text(statement), {"id": identifier, "u": USERS["member"]})
    with boundary.runtime.begin() as db:
        context(db, USERS["member"])
        assert db.scalar(text("SELECT count(*) FROM qms_projects")) == 0
        assert db.scalar(text("SELECT count(*) FROM qms_project_steps")) == 0
        assert (
            db.execute(
                text(
                    "UPDATE qms_projects SET row_version=row_version+1,updated_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": p["id"]},
            ).rowcount
            == 0
        )
    boundary.call(
        "GET", f"/qms-projects/{p['id']}", role="member", expected=403 if subject != "user" else 401
    )


def test_http_csrf_and_cache_boundary(boundary: Boundary) -> None:
    grant(boundary)
    p = create(boundary)
    response = boundary.clients["member"].get(f"/qms-projects/{p['id']}")
    assert response.headers.get("cache-control") == "private, no-store"
    csrf = boundary.clients["member"].headers.pop("X-CSRF-Token")
    try:
        boundary.call(
            "PATCH",
            f"/qms-projects/{p['id']}",
            {"expected_version": 1, "name": "Denied CSRF"},
            role="member",
            expected=403,
        )
    finally:
        boundary.clients["member"].headers["X-CSRF-Token"] = csrf


def test_audit_failure_rolls_back_step_and_parent_together(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant(boundary)
    p = create(boundary)

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Synthetic step audit failure")

    monkeypatch.setattr(audit_service, "record_qms_project", fail)
    with pytest.raises(RuntimeError, match="Synthetic step audit failure"):
        boundary.call(
            "PATCH",
            f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
            step_patch(p, p["steps"][0], status="blocked", notes="Waiting for information"),
            role="member",
        )
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p


def test_direct_sql_incomplete_catalog_cannot_commit(boundary: Boundary) -> None:
    grant(boundary)
    with pytest.raises(DBAPIError), boundary.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                "INSERT INTO qms_projects(id,tenant_id,unit_id,code,name,journey_key,catalog_version,scope_summary,status,row_version,created_by_user_id,created_at,updated_at) VALUES(:id,:t,:u,'PARTIAL','Partial','initial','guided-qms-v1','','open',1,:actor,now(),now())"
            ),
            {"id": uuid4(), "t": A, "u": SITE, "actor": USERS["member"]},
        )


def test_catalog_and_dependency_projection_are_runtime_immutable(boundary: Boundary) -> None:
    grant(boundary)
    create(boundary)
    for statement in (
        "DELETE FROM qms_project_catalog",
        "UPDATE qms_project_catalog SET feature_pending=false",
        "SELECT * FROM qms_project_dependency_projection",
        "DELETE FROM qms_projects",
    ):
        with pytest.raises(DBAPIError), boundary.runtime.begin() as db:
            context(db, USERS["member"])
            db.execute(text(statement))


def test_detail_read_keeps_parent_and_steps_in_one_consistent_snapshot(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    from threading import Event

    from pmc_api import qms_projects

    grant(boundary)
    p = create(boundary)
    paused, resume = Event(), Event()
    original = qms_projects._detail

    def delayed(db: Any, row: Any) -> Any:
        if row.row_version == 1:
            paused.set()
            assert resume.wait(10)
        return original(db, row)

    monkeypatch.setattr(qms_projects, "_detail", delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        read = pool.submit(boundary.call, "GET", f"/qms-projects/{p['id']}", role="member")
        try:
            assert paused.wait(10)
            changed = boundary.call(
                "PATCH",
                f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
                step_patch(p, p["steps"][0], notes="Concurrent notes"),
                role="member",
            )
        finally:
            resume.set()
        result = read.result(timeout=10)
    assert result == changed


def new_unit(case: Boundary) -> str:
    unit = case.call(
        "POST",
        "/organization/units",
        {"unit_type": "department", "code": "PLAN-SCOPE", "name": "Synthetic planning scope"},
        expected=201,
    )
    grant(case, unit=unit["id"])
    return str(unit["id"])


def wait_for_lock(case: Boundary) -> None:
    from time import monotonic, sleep

    deadline = monotonic() + 10
    while monotonic() < deadline:
        with case.admin.connect() as db:
            waiting = db.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND usename='pmcloud_app' AND wait_event_type='Lock'"
                )
            )
        if waiting:
            return
        sleep(0.02)
    raise AssertionError("competing command did not block on a PostgreSQL lock")


@pytest.mark.parametrize("first", ["project", "unit_archive"])
def test_unit_archive_and_project_creation_interleavings_use_scope_lock(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    from threading import Event

    unit = new_unit(boundary)
    paused, resume = Event(), Event()
    writer = "record_qms_project" if first == "project" else "record_organization_unit_archived"
    original = getattr(audit_service, writer)

    def pause(*args: Any, **kwargs: Any) -> Any:
        paused.set()
        assert resume.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(audit_service, writer, pause)

    def project() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .post(
                "/qms-projects",
                json={
                    "unit_id": unit,
                    "code": "RACE",
                    "name": "Synthetic race",
                    "journey_key": "initial",
                },
            )
            .status_code,
        )

    def archive() -> int:
        return cast(
            int, boundary.clients["owner"].post(f"/organization/units/{unit}/archive").status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_task = pool.submit(project if first == "project" else archive)
        try:
            assert paused.wait(10)
            second_task = pool.submit(archive if first == "project" else project)
            wait_for_lock(boundary)
        finally:
            resume.set()
        results = first_task.result(timeout=10), second_task.result(timeout=10)
    assert results == ((201, 409) if first == "project" else (200, 409))
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM qms_projects p JOIN organization_units u ON u.id=p.unit_id WHERE p.status='open' AND u.status='archived'"
                )
            )
            == 0
        )


def test_archived_project_history_hidden_with_unit_until_unit_restore(boundary: Boundary) -> None:
    unit = new_unit(boundary)
    p = create(boundary, unit=unit)
    archived = boundary.call(
        "POST",
        f"/qms-projects/{p['id']}/status",
        {"expected_version": 1, "target_status": "archived", "reason": "Retain historical project"},
        role="member",
    )
    boundary.call("POST", f"/organization/units/{unit}/archive")
    boundary.call("GET", f"/qms-projects/{p['id']}", role="member", expected=404)
    boundary.call("GET", f"/qms-projects?unit_id={unit}", role="member", expected=403)
    boundary.call("POST", f"/organization/units/{unit}/restore")
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == archived
    resumed = boundary.call(
        "POST",
        f"/qms-projects/{p['id']}/status",
        {
            "expected_version": 2,
            "target_status": "open",
            "reason": "Resume after scope restoration",
        },
        role="member",
    )
    assert resumed["row_version"] == 3 and resumed["status"] == "open"


@pytest.mark.parametrize("first", ["step", "archive"])
def test_project_archive_and_step_edit_serialize_on_parent(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    from threading import Event

    grant(boundary)
    p = create(boundary)
    paused, resume = Event(), Event()
    original = audit_service.record_qms_project

    def pause(*args: Any, **kwargs: Any) -> Any:
        paused.set()
        assert resume.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(audit_service, "record_qms_project", pause)

    def step() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .patch(
                f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
                json=step_patch(p, p["steps"][0], notes="Concurrent step draft"),
            )
            .status_code,
        )

    def archive() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .post(
                f"/qms-projects/{p['id']}/status",
                json={
                    "expected_version": 1,
                    "target_status": "archived",
                    "reason": "Concurrent archive",
                },
            )
            .status_code,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_task = pool.submit(step if first == "step" else archive)
        try:
            assert paused.wait(10)
            second_task = pool.submit(archive if first == "step" else step)
            wait_for_lock(boundary)
        finally:
            resume.set()
        assert (first_task.result(timeout=10), second_task.result(timeout=10)) == (200, 409)
    final = boundary.call("GET", f"/qms-projects/{p['id']}", role="member")
    assert final["row_version"] == 2
    assert final["status"] == ("open" if first == "step" else "archived")


@pytest.mark.parametrize("history", ["grant", "revoked_grant", "audit"])
def test_downgrade_preserves_grant_and_audit_history_without_projects(
    boundary: Boundary, history: str
) -> None:
    import subprocess
    import sys

    grant(boundary, manage=False)
    if history == "revoked_grant":
        grants = boundary.call("GET", "/qms-access/grants")
        identifier = next(g["id"] for g in grants if g["capability"] == "projects.read")
        boundary.call("POST", f"/qms-access/grants/{identifier}/revoke")
    if history == "audit":
        with boundary.admin.begin() as db:
            db.execute(text("TRUNCATE qms_access_grants CASCADE"))
    with boundary.admin.connect() as db:
        previous_revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0049_tenant_suspension"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "cannot discard QMS project history" in result.stderr
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT bool_and(relforcerowsecurity) FROM pg_class WHERE oid IN ('qms_projects'::regclass,'qms_project_steps'::regclass,'qms_access_grants'::regclass,'audit_events'::regclass)"
                )
            )
            is True
        )
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == previous_revision


def test_inactive_assignee_is_preserved_on_unrelated_notes_and_audit_is_private(
    boundary: Boundary,
) -> None:
    import hashlib

    grant(boundary)
    p = create(boundary)
    step = p["steps"][0]
    p = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}/steps/{step['id']}",
        step_patch(p, step, assignee_user_id=str(USERS["admin"]), notes="Synthetic private notes"),
        role="member",
    )
    with boundary.admin.begin() as db:
        db.execute(
            text("UPDATE memberships SET status='revoked' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["admin"]},
        )
    p = boundary.call(
        "PATCH",
        f"/qms-projects/{p['id']}/steps/{step['id']}",
        step_patch(p, p["steps"][0], notes="Preserved historical assignment"),
        role="member",
    )
    assert p["row_version"] == 3 and p["steps"][0]["row_version"] == 3
    assert p["steps"][0]["assignee_user_id"] == str(USERS["admin"])
    with boundary.admin.connect() as db:
        event = db.execute(
            text(
                "SELECT new_values,old_values,changed_fields FROM audit_events WHERE resource_id=:id AND action='qms_project_step.updated' ORDER BY occurred_at DESC LIMIT 1"
            ),
            {"id": step["id"]},
        ).one()
        assert (
            event.new_values["notes_hash"]
            == hashlib.sha256(b"Preserved historical assignment").hexdigest()
        )
        assert "notes" not in event.new_values and "notes" not in event.old_values
        assert {"notes_hash", "row_version", "project_row_version"} <= set(event.changed_fields)


def test_distinct_units_do_not_share_read_authority_or_step_parentage(boundary: Boundary) -> None:
    grant(boundary)
    first = create(boundary)
    unit = new_unit(boundary)
    other = create(boundary, code="PLAN-OTHER", unit=unit)
    grant(boundary, "auditor", manage=False)
    boundary.call("GET", f"/qms-projects/{other['id']}", role="auditor", expected=404)
    boundary.call("GET", f"/qms-projects?unit_id={unit}", role="auditor", expected=403)
    assert boundary.call("GET", f"/qms-projects/{first['id']}", role="auditor")["id"] == first["id"]
    boundary.call(
        "PATCH",
        f"/qms-projects/{other['id']}/steps/{first['steps'][0]['id']}",
        step_patch(other, first["steps"][0], notes="Cross parent denied"),
        role="member",
        expected=404,
    )
    assert boundary.call("GET", f"/qms-projects/{first['id']}", role="member") == first


def test_active_second_company_actor_cannot_read_first_company_project(boundary: Boundary) -> None:
    grant(boundary)
    first = create(boundary)
    with boundary.admin.begin() as db:
        context(db, USERS["owner"], B)
        for cap in ("projects.read", "projects.manage"):
            db.execute(
                text(
                    "INSERT INTO qms_access_grants(id,tenant_id,user_id,unit_id,capability,status,granted_by_user_id,created_at) VALUES(:id,:tenant,:user,:unit,:cap,'active',:user,now())"
                ),
                {"id": uuid4(), "tenant": B, "user": USERS["owner"], "unit": B_SITE, "cap": cap},
            )
        db.execute(
            text("UPDATE application_sessions SET current_tenant_id=:tenant WHERE user_id=:user"),
            {"tenant": B, "user": USERS["owner"]},
        )
    second = boundary.call(
        "POST",
        "/qms-projects",
        {
            "unit_id": str(B_SITE),
            "code": "PLAN-001",
            "name": "Second company project",
            "journey_key": "initial",
        },
        expected=201,
    )
    assert second["tenant_id"] == str(B)
    boundary.call("GET", f"/qms-projects/{first['id']}", expected=404)
    with boundary.runtime.begin() as db:
        context(db, USERS["owner"], B)
        assert db.scalar(text("SELECT count(*) FROM qms_projects")) == 1
        assert (
            db.scalar(text("SELECT count(*) FROM qms_projects WHERE id=:id"), {"id": first["id"]})
            == 0
        )
        assert db.scalar(text("SELECT count(*) FROM qms_project_steps")) == 8
    boundary.call("GET", f"/qms-projects/{second['id']}", role="member", expected=404)


def test_concurrent_duplicate_create_inserts_catalog_once_and_one_audit(boundary: Boundary) -> None:
    grant(boundary)

    def request() -> int:
        return cast(
            int,
            boundary.clients["member"]
            .post(
                "/qms-projects",
                json={
                    "unit_id": str(SITE),
                    "code": "RACE-CODE",
                    "name": "Concurrent project",
                    "journey_key": "initial",
                },
            )
            .status_code,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(request), pool.submit(request)]
        assert sorted(task.result(timeout=10) for task in tasks) == [201, 409]
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM qms_projects")) == 1
        assert db.scalar(text("SELECT count(*) FROM qms_project_steps")) == 8
        assert (
            db.scalar(text("SELECT count(*) FROM audit_events WHERE action='qms_project.created'"))
            == 1
        )


@pytest.mark.parametrize(
    "tampering", ["fake_journey", "fake_step", "gap_relabel", "partial_catalog", "wrong_order"]
)
def test_temporary_catalog_cannot_override_frozen_project_templates(
    boundary: Boundary, tampering: str
) -> None:
    """Runtime TEMP permission must never replace the trusted public catalog."""
    grant(boundary)
    identifier = uuid4()
    journey = "forged" if tampering == "fake_journey" else "initial"
    # These writes must fail even though each supplied temporary template is
    # internally consistent. The public frozen catalog is the only authority.
    with pytest.raises(DBAPIError) as rejected, boundary.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                "CREATE TEMP TABLE qms_project_catalog ON COMMIT DROP AS "
                "SELECT * FROM public.qms_project_catalog WITH NO DATA"
            )
        )
        if tampering == "gap_relabel":
            db.execute(
                text(
                    "INSERT INTO pg_temp.qms_project_catalog "
                    "SELECT catalog_version,journey_key,step_key,position,false "
                    "FROM public.qms_project_catalog WHERE journey_key='initial'"
                )
            )
        elif tampering in {"partial_catalog", "wrong_order"}:
            db.execute(
                text(
                    "INSERT INTO pg_temp.qms_project_catalog "
                    "SELECT catalog_version,journey_key,step_key,:position,feature_pending "
                    "FROM public.qms_project_catalog WHERE journey_key='initial' "
                    "AND step_key='process-map'"
                ),
                {"position": 9 if tampering == "wrong_order" else 1},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO pg_temp.qms_project_catalog "
                    "VALUES('guided-qms-v1',:journey,'forged-step',1,false)"
                ),
                {"journey": journey},
            )
        db.execute(
            text(
                "INSERT INTO public.qms_projects("
                "id,tenant_id,unit_id,code,name,journey_key,catalog_version,scope_summary,"
                "status,row_version,created_by_user_id,created_at,updated_at) "
                "VALUES(:id,:tenant,:unit,'TEMP-CATALOG','Synthetic tampering',:journey,"
                "'guided-qms-v1','','open',1,:actor,now(),now())"
            ),
            {
                "id": identifier,
                "tenant": A,
                "unit": SITE,
                "journey": journey,
                "actor": USERS["member"],
            },
        )
        db.execute(
            text(
                "INSERT INTO public.qms_project_steps("
                "id,tenant_id,unit_id,project_id,step_key,position,status,notes,"
                "row_version,source_project_version,updated_by_user_id,updated_at) "
                "SELECT gen_random_uuid(),:tenant,:unit,:id,step_key,position,"
                "'not_started','',1,1,:actor,now() FROM pg_temp.qms_project_catalog"
            ),
            {"id": identifier, "tenant": A, "unit": SITE, "actor": USERS["member"]},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert sqlstate(rejected.value) == "23514"
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.qms_projects WHERE id=:id"), {"id": identifier}
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.qms_project_steps WHERE project_id=:id"),
                {"id": identifier},
            )
            == 0
        )


def test_temporary_parent_and_steps_cannot_satisfy_deferred_completeness(
    boundary: Boundary,
) -> None:
    """Eight fake temporary children cannot justify a real childless project."""
    grant(boundary)
    identifier = uuid4()
    with pytest.raises(DBAPIError) as rejected, boundary.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                "INSERT INTO public.qms_projects("
                "id,tenant_id,unit_id,code,name,journey_key,catalog_version,scope_summary,"
                "status,row_version,created_by_user_id,created_at,updated_at) "
                "VALUES(:id,:tenant,:unit,'TEMP-COMPLETE','Synthetic tampering','initial',"
                "'guided-qms-v1','','open',1,:actor,now(),now())"
            ),
            {"id": identifier, "tenant": A, "unit": SITE, "actor": USERS["member"]},
        )
        db.execute(
            text(
                "CREATE TEMP TABLE qms_projects ON COMMIT DROP AS "
                "SELECT * FROM public.qms_projects WHERE id=:id"
            ),
            {"id": identifier},
        )
        db.execute(
            text(
                "CREATE TEMP TABLE qms_project_steps ON COMMIT DROP AS "
                "SELECT * FROM public.qms_project_steps WITH NO DATA"
            )
        )
        db.execute(
            text(
                "INSERT INTO pg_temp.qms_project_steps(project_id) "
                "SELECT :id FROM generate_series(1,8)"
            ),
            {"id": identifier},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert sqlstate(rejected.value) == "23514"
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.qms_projects WHERE id=:id"), {"id": identifier}
            )
            == 0
        )


def _direct_versioned_step_notes(
    case: Boundary, project: dict[str, Any], *, status: str, notes: str
) -> None:
    """Exercise the real note CHECK after satisfying parent/version/actor guards."""
    step = project["steps"][0]
    with case.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                "UPDATE public.qms_projects SET row_version=row_version+1,"
                "step_write_id=:step,updated_at=greatest(clock_timestamp(),updated_at+interval '1 microsecond') WHERE id=:project"
            ),
            {"step": step["id"], "project": project["id"]},
        )
        db.execute(
            text(
                "UPDATE public.qms_project_steps SET status=:status,notes=:notes,"
                "row_version=row_version+1,source_project_version=:version,"
                "updated_by_user_id=:actor,updated_at=greatest(clock_timestamp(),updated_at+interval '1 microsecond') WHERE id=:step"
            ),
            {
                "status": status,
                "notes": notes,
                "version": project["row_version"] + 1,
                "actor": USERS["member"],
                "step": step["id"],
            },
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.parametrize("status", ["blocked", "reported"])
@pytest.mark.parametrize(
    "notes",
    [
        "",
        " \t\n\r",
        "\v",
        "\f",
        "\x1c\x1d\x1e\x1f",
        "\x85\u00a0",
        "\u1680\u2003\u2028\u2029\u202f\u205f\u3000",
        "".join(chr(codepoint) for codepoint in range(0x110000) if chr(codepoint).isspace()),
    ],
    ids=[
        "empty",
        "ascii",
        "vertical-tab",
        "form-feed",
        "controls",
        "c1-nbsp",
        "unicode",
        "all-python-whitespace",
    ],
)
def test_direct_sql_rejects_python_strip_empty_notes(
    boundary: Boundary, status: str, notes: str
) -> None:
    # Python's current API runtime is an independent oracle for meaningful notes.
    assert not notes.strip()
    grant(boundary)
    project = create(boundary)
    with pytest.raises(DBAPIError) as rejected:
        _direct_versioned_step_notes(boundary, project, status=status, notes=notes)
    assert sqlstate(rejected.value) == "23514"
    assert boundary.call("GET", f"/qms-projects/{project['id']}", role="member") == project


@pytest.mark.parametrize("status", ["blocked", "reported"])
@pytest.mark.parametrize(
    "notes", ["Documented work pending verification", "\v\u00a0 Trabajo documentado \u3000\f"]
)
def test_direct_sql_preserves_meaningful_notes_and_versions(
    boundary: Boundary, status: str, notes: str
) -> None:
    assert notes.strip()
    grant(boundary)
    project = create(boundary)
    _direct_versioned_step_notes(boundary, project, status=status, notes=notes)
    result = boundary.call("GET", f"/qms-projects/{project['id']}", role="member")
    assert result["row_version"] == 2
    assert result["steps"][0]["row_version"] == 2
    assert result["steps"][0]["status"] == status
    assert result["steps"][0]["notes"] == notes


def _direct_complete_project_text(
    case: Boundary, identifier: UUID, *, code: str, name: str
) -> None:
    with case.runtime.begin() as db:
        context(db, USERS["member"])
        db.execute(
            text(
                "INSERT INTO public.qms_projects(id,tenant_id,unit_id,code,name,journey_key,"
                "catalog_version,scope_summary,status,row_version,created_by_user_id,created_at,updated_at) "
                "VALUES(:id,:tenant,:unit,:code,:name,'initial','guided-qms-v1','','open',1,:actor,now(),now())"
            ),
            {
                "id": identifier,
                "tenant": A,
                "unit": SITE,
                "code": code,
                "name": name,
                "actor": USERS["member"],
            },
        )
        db.execute(
            text(
                "INSERT INTO public.qms_project_steps(id,tenant_id,unit_id,project_id,step_key,position,"
                "status,notes,row_version,source_project_version,updated_by_user_id,updated_at) "
                "SELECT gen_random_uuid(),:tenant,:unit,:id,step_key,position,"
                "CASE WHEN feature_pending THEN 'feature_pending' ELSE 'not_started' END,"
                "'',1,1,:actor,now() FROM public.qms_project_catalog WHERE journey_key='initial' "
                "AND catalog_version='guided-qms-v1'"
            ),
            {"id": identifier, "tenant": A, "unit": SITE, "actor": USERS["member"]},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.parametrize("field", ["code", "name"])
@pytest.mark.parametrize(
    "value",
    [
        "\t",
        "\u00a0\u2003",
        "\ufeff",
        "".join(chr(point) for point in range(0x110000) if chr(point).isspace()) + "\ufeff",
        "\ufeffPlan",
        "Plan\u3000",
    ],
    ids=["tab-blank", "unicode-blank", "bom-blank", "all-blank", "leading-bom", "trailing-unicode"],
)
def test_direct_sql_identity_requires_nonblank_normalized_project_text(
    boundary: Boundary, field: str, value: str
) -> None:
    grant(boundary)
    identifier = uuid4()
    values = {"code": "DIRECT-PLAN", "name": "Direct project", field: value}
    with pytest.raises(DBAPIError) as rejected:
        _direct_complete_project_text(boundary, identifier, **values)
    assert sqlstate(rejected.value) == "23514"
    with boundary.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.qms_projects WHERE id=:id"), {"id": identifier}
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM public.qms_project_steps WHERE project_id=:id"),
                {"id": identifier},
            )
            == 0
        )


def test_direct_sql_preserves_meaningful_internal_identity_characters(boundary: Boundary) -> None:
    grant(boundary)
    identifier = uuid4()
    code, name = "A\ufeff \t\u2003B", "Plan \ufeff interno\tUnicode"
    _direct_complete_project_text(boundary, identifier, code=code, name=name)
    project = boundary.call("GET", f"/qms-projects/{identifier}", role="member")
    assert project["code"] == code and project["name"] == name and len(project["steps"]) == 8


@pytest.mark.parametrize("status", ["blocked", "reported"])
def test_direct_sql_rejects_bom_only_required_notes(boundary: Boundary, status: str) -> None:
    grant(boundary)
    project = create(boundary)
    with pytest.raises(DBAPIError) as rejected:
        _direct_versioned_step_notes(boundary, project, status=status, notes="\ufeff")
    assert sqlstate(rejected.value) == "23514"
    assert boundary.call("GET", f"/qms-projects/{project['id']}", role="member") == project


def test_http_normalization_and_supplementary_unicode_limits(boundary: Boundary) -> None:
    grant(boundary)
    code, name, scope, notes = (
        "\U0001f9ed" * 40,
        "\U0001f680" * 160,
        "\U0001f9ea" * 4000,
        "\U0001f4dd" * 2000,
    )
    project = boundary.call(
        "POST",
        "/qms-projects",
        {
            "unit_id": str(SITE),
            "code": "\ufeff" + code + "\ufeff",
            "name": "\u3000" + name + "\ufeff",
            "scope_summary": scope,
            "journey_key": "initial",
        },
        role="member",
        expected=201,
    )
    assert project["code"] == code and project["name"] == name and project["scope_summary"] == scope
    updated = boundary.call(
        "PATCH",
        f"/qms-projects/{project['id']}/steps/{project['steps'][0]['id']}",
        step_patch(project, project["steps"][0], status="reported", notes=notes),
        role="member",
    )
    assert updated["code"] == code and updated["name"] == name and updated["scope_summary"] == scope
    assert updated["steps"][0]["notes"] == notes and updated["row_version"] == 2


def test_http_rejects_bom_only_project_values_and_current_required_notes(
    boundary: Boundary,
) -> None:
    grant(boundary)
    body = {"unit_id": str(SITE), "code": "PLAN", "name": "Plan", "journey_key": "initial"}
    for field in ("code", "name"):
        boundary.call(
            "POST", "/qms-projects", {**body, field: "\ufeff"}, role="member", expected=422
        )
    project = create(boundary)
    path = f"/qms-projects/{project['id']}"
    boundary.call(
        "PATCH", path, {"expected_version": 1, "name": "\ufeff"}, role="member", expected=422
    )
    boundary.call(
        "POST",
        path + "/status",
        {"expected_version": 1, "target_status": "archived", "reason": "\ufeff"},
        role="member",
        expected=422,
    )
    step = project["steps"][0]
    boundary.call(
        "PATCH",
        path + f"/steps/{step['id']}",
        step_patch(project, step, status="reported", notes="\ufeff"),
        role="member",
        expected=422,
    )
    reported = boundary.call(
        "PATCH",
        path + f"/steps/{step['id']}",
        step_patch(project, step, status="reported", notes="Meaningful self report"),
        role="member",
    )
    boundary.call(
        "PATCH",
        path + f"/steps/{step['id']}",
        step_patch(reported, reported["steps"][0], notes="\ufeff"),
        role="member",
        expected=422,
    )
    assert boundary.call("GET", path, role="member") == reported
