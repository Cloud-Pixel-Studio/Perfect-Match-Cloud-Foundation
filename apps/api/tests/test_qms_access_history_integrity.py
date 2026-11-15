# ruff: noqa: E501
"""Real RLS and HTTP pagination over synthetic grants in a disposable database."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.database import get_db
from pmc_api.main import app

pytestmark = [
    pytest.mark.qms_access_history_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable access-history PostgreSQL",
    ),
]
A, B = UUID("95000000-0000-4000-8000-000000000001"), UUID("95000000-0000-4000-8000-000000000002")
USERS = {
    role: UUID(f"96000000-0000-4000-8000-{i:012d}")
    for i, role in enumerate(("owner", "admin", "member", "auditor", "other_owner", "b_member"), 1)
}
UNITS = [UUID(f"97000000-0000-4000-8000-{i:012d}") for i in range(1, 7)]
CAPS = (
    "documents.read",
    "evidence.read",
    "processes.read",
    "controls.read",
    "control_instances.read",
    "risks.read",
    "ncr.read",
    "capa.read",
    "audits.read",
    "audits.execute",
)
PAGE = "/qms-access/grants/page"


@dataclass
class History:
    admin: Engine
    runtime: Engine
    clients: dict[str, TestClient]
    rows: list[dict[str, Any]]

    def page(self, role: str = "owner", expected: int = 200, **params: Any) -> dict[str, Any]:
        response = self.clients[role].get(PAGE, params=params)
        assert response.status_code == expected, (response.status_code, response.text)
        if expected == 200:
            assert response.headers.get("cache-control") == "private, no-store"
        data = response.json()
        assert isinstance(data, dict)
        return data

    def all(self, role: str = "owner", **filters: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor = None
        seen: set[str] = set()
        while True:
            page = self.page(role, **filters, **({"cursor": cursor} if cursor else {}))
            assert page["tenant_id"] == str(A)
            assert page["viewer_user_id"] == str(USERS[role])
            assert page["viewer_role"] == ("owner" if role == "other_owner" else role)
            assert "total" not in page
            result.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                return result
            assert cursor not in seen
            seen.add(cursor)
            assert len(seen) < 200

    def suspend(self, subject: str = "tenant") -> None:
        sql = {
            "tenant": "UPDATE tenants SET status='disabled' WHERE id=:id",
            "user": "UPDATE users SET status='disabled' WHERE id=:u",
            "membership": "UPDATE memberships SET status='revoked' WHERE tenant_id=:id AND user_id=:u",
            "role": "UPDATE memberships SET role='member' WHERE tenant_id=:id AND user_id=:u",
        }[subject]
        with self.admin.begin() as db:
            db.execute(text(sql), {"id": A, "u": USERS["owner"]})


@pytest.fixture
def history() -> Iterator[History]:
    admin_url, runtime_url = (
        os.environ["PMC_TEST_ADMIN_DATABASE_URL"],
        os.environ["PMC_TEST_RUNTIME_DATABASE_URL"],
    )
    assert (
        make_url(admin_url).database == make_url(runtime_url).database == "pmcloud_access_history"
    )
    admin, runtime = create_engine(admin_url), create_engine(runtime_url)
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    with admin.begin() as db:
        db.execute(text("TRUNCATE tenants,users CASCADE"))
        for tenant in (A, B):
            db.execute(
                text(
                    "INSERT INTO tenants(id,name,slug,status,created_at,updated_at) VALUES(:id,:n,:slug,'active',:now,:now)"
                ),
                {"id": tenant, "n": "Synthetic company", "slug": str(tenant), "now": now},
            )
        for role, user in USERS.items():
            db.execute(
                text(
                    "INSERT INTO users(id,display_name,status,created_at) VALUES(:id,:n,'active',:now)"
                ),
                {"id": user, "n": f"Synthetic {role.replace('_', ' ')}", "now": now},
            )
            for tenant in (B,) if role == "b_member" else ((A, B) if role == "owner" else (A,)):
                db.execute(
                    text(
                        "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) VALUES(:id,:t,:u,:r,'active',:now)"
                    ),
                    {
                        "id": uuid4(),
                        "t": tenant,
                        "u": user,
                        "r": "owner"
                        if role in ("owner", "other_owner")
                        else ("member" if role == "b_member" else role),
                        "now": now,
                    },
                )
        for index, unit in enumerate(UNITS):
            db.execute(
                text(
                    "INSERT INTO organization_units(id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES(:id,:t,'team',:c,:n,'active',:now,:now)"
                ),
                {
                    "id": unit,
                    "t": B if index == 5 else A,
                    "c": f"UNIT{index}",
                    "n": "Calibration %_ line" if index == 0 else f"Synthetic scope {index}",
                    "now": now,
                },
            )
        # Administrative seeding is synthetic; database grant validation triggers still run.
        db.execute(
            text("SELECT set_config('app.user_id',:u,true),set_config('app.tenant_id',:t,true)"),
            {"u": str(USERS["owner"]), "t": str(A)},
        )
        index = 0
        for role in ("admin", "member", "auditor"):
            for unit in UNITS[:5]:
                for capability in CAPS:
                    index += 1
                    rows.append(
                        {
                            "id": UUID(f"98000000-0000-4000-8000-{index:012d}"),
                            "t": A,
                            "u": USERS[role],
                            "unit": unit,
                            "cap": capability,
                            "status": "active",
                            "at": now - timedelta(days=1) if index == 1 else now,
                            "revoker": None,
                            "revoked": None,
                        }
                    )
        for offset in range(5):
            rows.append(
                {
                    "id": UUID(f"99000000-0000-4000-8000-{offset + 1:012d}"),
                    "t": A,
                    "u": USERS["member"],
                    "unit": UNITS[0],
                    "cap": "documents.read",
                    "status": "revoked",
                    "at": now - timedelta(days=2),
                    "revoker": USERS["owner"],
                    "revoked": now,
                }
            )
        for row in rows:
            db.execute(
                text(
                    "INSERT INTO qms_access_grants(id,tenant_id,user_id,unit_id,capability,status,granted_by_user_id,created_at,revoked_by_user_id,revoked_at) VALUES(:id,:t,:u,:unit,:cap,:status,:owner,:at,:revoker,:revoked)"
                ),
                {**row, "owner": USERS["owner"]},
            )
        db.execute(text("SELECT set_config('app.tenant_id',:t,true)"), {"t": str(B)})
        db.execute(
            text(
                "INSERT INTO qms_access_grants(id,tenant_id,user_id,unit_id,capability,status,granted_by_user_id,created_at) VALUES(:id,:t,:u,:unit,'documents.read','active',:owner,:at)"
            ),
            {
                "id": uuid4(),
                "t": B,
                "u": USERS["b_member"],
                "unit": UNITS[5],
                "owner": USERS["owner"],
                "at": now,
            },
        )

    def override() -> Iterator[Session]:
        with Session(runtime, expire_on_commit=False) as db:
            try:
                yield db
            finally:
                db.rollback()

    app.dependency_overrides[get_db] = override
    clients = {}
    try:
        for role, user in USERS.items():
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            with admin.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO application_sessions(id,user_id,token_hash,current_tenant_id,csrf_token_hash,created_at,expires_at,last_seen_at) VALUES(:id,:u,:h,:t,:c,:now,:expires,:now)"
                    ),
                    {
                        "id": uuid4(),
                        "u": user,
                        "h": hashlib.sha256(token.encode()).digest(),
                        "t": B if role == "b_member" else A,
                        "c": hashlib.sha256(csrf.encode()).digest(),
                        "now": now,
                        "expires": now + timedelta(hours=1),
                    },
                )
            client = TestClient(app)
            client.cookies.set("pm_session", token)
            client.cookies.set("pm_csrf", csrf)
            client.headers["X-CSRF-Token"] = csrf
            clients[role] = client
        yield History(admin, runtime, clients, rows)
    finally:
        app.dependency_overrides.pop(get_db, None)
        for client in clients.values():
            client.close()
        admin.dispose()
        runtime.dispose()


def test_complete_pages_preserve_timestamp_ties_and_legacy_cap(history: History) -> None:
    expected = sorted(history.rows, key=lambda row: (-row["at"].timestamp(), row["id"]))
    rows = history.all(limit=17)
    assert [row["id"] for row in rows] == [str(row["id"]) for row in expected]
    assert len({row["id"] for row in rows}) == 155
    assert all(row["member_name"] and row["unit_name"] and row["unit_code"] for row in rows)
    assert all(row["unit_status"] == "active" for row in rows)
    legacy = history.clients["owner"].get("/qms-access/grants")
    assert (
        legacy.status_code == 200 and isinstance(legacy.json(), list) and len(legacy.json()) == 100
    )
    assert len(history.page()["items"]) == 20


@pytest.mark.parametrize(
    "role,expected",
    [("owner", 155), ("other_owner", 155), ("admin", 50), ("member", 55), ("auditor", 50)],
)
def test_roles_only_receive_rls_visible_grants(history: History, role: str, expected: int) -> None:
    rows = history.all(role, limit=100)
    assert len(rows) == expected
    if role not in ("owner", "other_owner"):
        assert all(row["user_id"] == str(USERS[role]) for row in rows)
        history.page(
            role, expected=403, user_id=str(USERS["member"] if role != "member" else USERS["admin"])
        )
    assert all(row["unit_id"] != str(UNITS[5]) for row in rows)


@pytest.mark.parametrize("status,expected", [("all", 155), ("active", 150), ("revoked", 5)])
def test_status_filters_span_all_pages(history: History, status: str, expected: int) -> None:
    rows = history.all(status=status, limit=23)
    assert len(rows) == expected
    assert status == "all" or all(row["status"] == status for row in rows)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("%", 35),
        ("%_", 35),
        ("_", 47),
        ("  %_  ", 35),
        ("Synthetic member", 55),
        ("not-present", 0),
        ("documents.read", 20),
    ],
)
def test_search_matches_literal_patterns_and_labels(
    history: History, query: str, expected: int
) -> None:
    assert len(history.all(q=query, limit=100)) == expected


def test_scoped_filters_ids_and_known_capability(history: History) -> None:
    rows = history.all(
        user_id=str(USERS["member"]), unit_id=str(UNITS[0]), capability="documents.read"
    )
    assert len(rows) == 6
    assert all(
        row["user_id"] == str(USERS["member"])
        and row["unit_id"] == str(UNITS[0])
        and row["capability"] == "documents.read"
        for row in rows
    )
    assert len(history.all(q=str(USERS["member"]), limit=100)) == 55
    assert len(history.all(q=str(history.rows[0]["id"]))) == 1
    assert history.page(unit_id=str(UNITS[5]))["items"] == []
    assert history.page(user_id=str(USERS["b_member"]))["items"] == []
    assert history.page(unit_id=str(uuid4()))["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"status": "unknown"},
        {"capability": "platform.root"},
        {"user_id": "not-a-uuid"},
        {"q": "x" * 161},
    ],
)
def test_invalid_query_rejected(history: History, params: dict[str, Any]) -> None:
    history.page(expected=422, **params)


@pytest.mark.parametrize("cursor", ["!", "e30=", "bm90LWpzb24=", "x" * 1000])
def test_malformed_cursor_rejected(history: History, cursor: str) -> None:
    history.page(expected=400, cursor=cursor)


def test_cursor_is_bound_to_actor_tenant_role_filters_and_limit(history: History) -> None:
    page = history.page(limit=11)
    cursor = page["next_cursor"]
    assert cursor
    assert history.page(limit=11, cursor=cursor) == history.page(limit=11, cursor=cursor)
    for params in (
        {"limit": 12},
        {"limit": 11, "status": "active"},
        {"limit": 11, "q": "member"},
        {"limit": 11, "unit_id": str(UNITS[0])},
        {"limit": 11, "user_id": str(USERS["member"])},
        {"limit": 11, "capability": "documents.read"},
    ):
        history.page(expected=409, cursor=cursor, **params)
    history.page("other_owner", expected=409, limit=11, cursor=cursor)
    response = history.clients["owner"].post("/auth/tenant", json={"tenant_id": str(B)})
    assert response.status_code == 200
    history.page(expected=409, limit=11, cursor=cursor)


@pytest.mark.parametrize(
    "subject,expected", [("tenant", 403), ("membership", 403), ("user", 401), ("role", 409)]
)
def test_cursor_continuation_rechecks_current_identity(
    history: History, subject: str, expected: int
) -> None:
    cursor = history.page(limit=2)["next_cursor"]
    history.suspend(subject)
    history.page(expected=expected, limit=2, cursor=cursor)


def test_revocation_of_old_grant_is_visible_and_has_atomic_ledger(history: History) -> None:
    oldest = str(history.rows[0]["id"])
    assert oldest not in {row["id"] for row in history.page(limit=100)["items"]}
    response = history.clients["owner"].post(f"/qms-access/grants/{oldest}/revoke")
    assert response.status_code == 200
    found = history.page(q=oldest)["items"]
    assert len(found) == 1 and found[0]["status"] == "revoked"
    assert found[0]["revoked_by_user_id"] == str(USERS["owner"])
    with history.admin.begin() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action='qms.access_revoked'"
                ),
                {"id": UUID(oldest)},
            )
            == 1
        )


def test_ledger_failure_rolls_back_revocation(
    history: History, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic ledger failure")

    monkeypatch.setattr(audit_service, "record_qms_access", fail)
    identifier = history.rows[0]["id"]
    with pytest.raises(RuntimeError, match="synthetic ledger failure"):
        history.clients["owner"].post(f"/qms-access/grants/{identifier}/revoke")
    with history.admin.begin() as db:
        assert (
            db.scalar(text("SELECT status FROM qms_access_grants WHERE id=:id"), {"id": identifier})
            == "active"
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_events WHERE resource_id=:id"), {"id": identifier}
            )
            == 0
        )


@pytest.mark.parametrize("subject", ["tenant", "membership", "role"])
def test_revalidation_discards_rows_if_access_changes_during_read(
    history: History, monkeypatch: pytest.MonkeyPatch, subject: str
) -> None:
    execute = Session.execute
    changed = False

    def intercept(self: Session, statement: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal changed
        result = execute(self, statement, *args, **kwargs)
        query = str(statement).lower()
        if (
            not changed
            and "qms_access_grants" in query
            and "limit" in query
            and "order by" in query
        ):
            frozen = result.freeze()
            changed = True
            history.suspend(subject)
            return frozen()
        return result

    monkeypatch.setattr(Session, "execute", intercept)
    history.page(expected=403)
    assert changed


def test_authority_query_is_not_truncated_by_history(history: History) -> None:
    response = history.clients["member"].get("/qms-access/active-capabilities")
    assert response.status_code == 200
    assert set(response.json()["capabilities"]) == set(CAPS)
    # Owner's administration does not implicitly grant QMS business authority.
    assert (
        history.clients["owner"].get("/qms-access/active-capabilities").json()["capabilities"] == []
    )


def test_unsigned_cursor_cannot_widen_nonowner_scope(history: History) -> None:
    cursor = history.page()["next_cursor"]
    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    payload["viewer_user_id"] = str(USERS["member"])
    payload["viewer_role"] = "member"
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    page = history.page("member", cursor=forged)
    assert page["items"]
    assert all(row["user_id"] == str(USERS["member"]) for row in page["items"])
    assert all(row["member_name"] == "Synthetic member" for row in page["items"])
    payload["viewer_role"] = "owner"
    escalated = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    history.page("member", expected=409, cursor=escalated)


def test_inactive_target_retains_history_without_directory_label(history: History) -> None:
    with history.admin.begin() as db:
        db.execute(
            text("UPDATE memberships SET status='revoked' WHERE tenant_id=:t AND user_id=:u"),
            {"t": A, "u": USERS["member"]},
        )
    rows = history.all(user_id=str(USERS["member"]), limit=100)
    assert len(rows) == 55
    assert all(row["member_name"] is None for row in rows)
    assert all(row["unit_name"] for row in rows)
    assert history.page(q="Synthetic member")["items"] == []


@pytest.mark.parametrize("path", ["/organization/members", "/organization/units"])
def test_owner_catalogues_are_correlated_to_current_company(history: History, path: str) -> None:
    response = history.clients["owner"].get(path)
    assert response.status_code == 200
    assert response.headers["x-tenant-id"] == str(A)
    assert response.headers["cache-control"] == "private, no-store"
    assert isinstance(response.json(), list)
