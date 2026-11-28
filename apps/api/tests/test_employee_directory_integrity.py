from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, A, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]

PATH = f"/employees/{A}"


def test_employee_lifecycle_persists_personnel_and_audit_without_creating_a_seat(
    boundary: Boundary,
) -> None:
    body = {"full_name": "  Elena Cruz  ", "job_title": "Quality technician", "unit_id": str(SITE)}
    row = boundary.call("POST", PATH, body, expected=201)
    assert (row["full_name"], row["status"], row["row_version"]) == ("Elena Cruz", "active", 1)
    url = f"{PATH}/{row['id']}"
    page = boundary.call("GET", f"{PATH}?search=elena", role="admin")
    assert page["items"] == [row]
    assert boundary.clients["admin"].get(PATH).headers["cache-control"] == "private, no-store"
    assert boundary.call("GET", f"{PATH}?search=%25")["items"] == []

    update = {**body, "job_title": "Quality lead", "expected_version": 1}
    modified = boundary.call("PATCH", url, update, role="admin")
    assert (modified["job_title"], modified["row_version"]) == ("Quality lead", 2)
    boundary.call("PATCH", url, update, expected=409)
    boundary.call("PATCH", url, {**update, "expected_version": 2}, role="admin")
    archived = boundary.call("POST", f"{url}/archive", {"expected_version": 2})
    assert (archived["status"], archived["row_version"]) == ("archived", 3)
    assert boundary.call("GET", PATH)["items"] == []
    assert boundary.call("GET", f"{PATH}?include_archived=true")["items"] == [archived]
    boundary.call("PATCH", url, {**update, "expected_version": 3}, expected=409)
    restored = boundary.call("POST", f"{url}/restore", {"expected_version": 3})
    assert (restored["status"], restored["row_version"]) == ("active", 4)

    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM memberships WHERE tenant_id=:t"), {"t": A}) == 4
        events = db.execute(
            text(
                "SELECT action, actor_user_id, old_values, new_values, metadata AS event_metadata "
                "FROM audit_events WHERE resource_id=:id ORDER BY occurred_at"
            ),
            {"id": UUID(row["id"])},
        ).all()
    assert [event.action for event in events] == [
        "employee.created",
        "employee.updated",
        "employee.archived",
        "employee.restored",
    ]
    assert events[1].actor_user_id == USERS["admin"]
    assert events[1].event_metadata["profile_fields"] == ["job_title"]
    assert "Elena Cruz" not in str(events) and "Quality lead" not in str(events)


def test_employee_authority_is_tenant_bound_in_api_and_database(boundary: Boundary) -> None:
    profile = {"full_name": "Synthetic employee", "job_title": "Inspector", "unit_id": str(SITE)}
    row = boundary.call("POST", PATH, profile, expected=201)
    for role in ("member", "auditor"):
        boundary.call("GET", PATH, role=role, expected=403)
        boundary.call("POST", PATH, profile, role=role, expected=403)
    boundary.call("POST", PATH, {**profile, "unit_id": str(B_SITE)}, expected=409)
    assert (
        boundary.clients["owner"].post(PATH, json=profile, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    boundary.call("GET", f"/employees/{B}", expected=409)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    path_b = f"/employees/{B}"
    assert boundary.call("GET", path_b)["items"] == []
    boundary.call("GET", PATH, expected=409)
    boundary.call("POST", f"{path_b}/{row['id']}/archive", {"expected_version": 1}, expected=404)

    for user, tenant in ((USERS["owner"], B), (USERS["member"], A), (USERS["auditor"], A)):
        with boundary.runtime.begin() as db:
            context(db, user=user, tenant=tenant)
            assert db.scalar(text("SELECT count(*) FROM employee_profiles")) == 0
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM employee_profiles")) == 1
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("DELETE FROM employee_profiles"))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                text("UPDATE employee_profiles SET unit_id=:unit, row_version=2"),
                {"unit": B_SITE},
            )
    boundary.change("tenant", False)
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(A)}, expected=403)
    with boundary.runtime.begin() as db:
        context(db)
        assert db.scalar(text("SELECT count(*) FROM employee_profiles")) == 0
