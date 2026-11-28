from __future__ import annotations

import os
from io import BytesIO
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image, PngImagePlugin
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, A, B, Boundary, context
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import employee_portraits
from pmc_api.antivirus import ScanUnavailable, ScanVerdict

pytestmark = [
    pytest.mark.tenant_suspension_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]

PATH = f"/employees/{A}"


def synthetic_portrait(color: str = "navy") -> bytes:
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Comment", "private-fixture-metadata")
    Image.new("RGB", (96, 128), color).save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def test_employee_portrait_lifecycle_and_access(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(employee_portraits, "scan", lambda _: ScanVerdict.CLEAN)
    body = {"full_name": "Synthetic Employee", "job_title": "Inspector", "unit_id": str(SITE)}
    row = boundary.call("POST", PATH, body, expected=201)
    url = f"{PATH}/{row['id']}"
    photo = f"{url}/photo"
    png = synthetic_portrait()
    headers = {"Content-Type": "image/png"}
    admin = boundary.clients["admin"]
    assert not row["has_portrait"]
    assert admin.get(photo).status_code == 404
    assert boundary.clients["member"].get(photo).status_code == 403
    assert (
        admin.put(
            photo + "?expected_version=1", content=png, headers={**headers, "X-CSRF-Token": ""}
        ).status_code
        == 403
    )
    reply = admin.put(photo + "?expected_version=1", content=png, headers=headers)
    assert reply.status_code == 200, reply.text
    assert reply.json()["has_portrait"] and reply.json()["row_version"] == 2
    fetched = admin.get(photo)
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.headers["cache-control"] == "private, no-store"
    assert fetched.headers["x-tenant-id"] == str(A)
    assert fetched.headers["cross-origin-resource-policy"] == "same-origin"
    assert b"private-fixture-metadata" not in fetched.content
    with Image.open(BytesIO(fetched.content)) as image:
        assert image.format == "JPEG" and image.size == (96, 128)
    with pytest.raises(DBAPIError, match="cannot discard employee portraits"):
        command.downgrade(Config("alembic.ini"), "0064_document_storage_quota")
    assert admin.get(photo).content == fetched.content
    assert admin.delete(photo + "?expected_version=1").status_code == 409
    updated = admin.put(
        photo + "?expected_version=2", content=synthetic_portrait("green"), headers=headers
    )
    assert updated.status_code == 200 and updated.json()["row_version"] == 3
    assert admin.get(photo).content != fetched.content
    assert boundary.call("POST", f"{url}/archive", {"expected_version": 3})["has_portrait"]
    assert admin.get(photo).status_code == 200
    assert admin.delete(photo + "?expected_version=4").status_code == 409
    boundary.call("POST", f"{url}/restore", {"expected_version": 4})
    boundary.call("POST", "/auth/tenant", {"tenant_id": str(B)})
    foreign = f"/employees/{B}/{row['id']}/photo"
    owner = boundary.clients["owner"]
    assert owner.get(photo).status_code == 409
    assert owner.get(foreign).status_code == 404
    assert owner.delete(foreign + "?expected_version=5").status_code == 404
    with boundary.runtime.begin() as db:
        context(db, user=USERS["owner"], tenant=B)
        assert db.scalar(text("SELECT count(portrait) FROM employee_profiles")) == 0
    removed = admin.delete(photo + "?expected_version=5")
    assert removed.status_code == 200 and not removed.json()["has_portrait"]
    assert admin.get(photo).status_code == 404
    with boundary.admin.connect() as db:
        events = db.execute(
            text("""
            SELECT actor_user_id, metadata AS event_metadata, old_values, new_values
            FROM audit_events WHERE resource_id = :id AND action = 'employee.updated'
            ORDER BY occurred_at
        """),
            {"id": UUID(row["id"])},
        ).all()
    assert len(events) == 3
    assert all(
        e.actor_user_id == USERS["admin"] and e.event_metadata["profile_fields"] == ["portrait"]
        for e in events
    )
    assert all(set(e.new_values) == {"unit_id", "status", "row_version"} for e in events)


def test_employee_portrait_validation_keeps_the_profile_intact(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = boundary.call(
        "POST",
        PATH,
        {
            "full_name": "Synthetic Employee",
            "job_title": "Inspector",
            "unit_id": str(SITE),
        },
        expected=201,
    )
    photo = f"{PATH}/{row['id']}/photo?expected_version=1"
    admin = boundary.clients["admin"]
    png = synthetic_portrait()
    headers = {"Content-Type": "image/png"}
    assert (
        admin.put(photo, content=png, headers={"Content-Type": "image/svg+xml"}).status_code == 415
    )
    assert admin.put(photo, content=png, headers={"Content-Type": "image/jpeg"}).status_code == 415
    assert admin.put(photo, content=b"a" * 2_000_001, headers=headers).status_code == 413
    monkeypatch.setattr(employee_portraits, "scan", lambda _: ScanVerdict.INFECTED)
    assert admin.put(photo, content=png, headers=headers).status_code == 422

    def unavailable(_: BytesIO) -> ScanVerdict:
        raise ScanUnavailable

    monkeypatch.setattr(employee_portraits, "scan", unavailable)
    assert admin.put(photo, content=png, headers=headers).status_code == 503
    assert boundary.call("GET", PATH)["items"] == [row]


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
