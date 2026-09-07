from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from pmc_api.main import app
from pmc_api.oidc import IdentityClaims, OIDCProvider
from pmc_api.security import TransactionCipher, generate_token, token_hash

pytestmark = [
    pytest.mark.tenant_isolation,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="tenant isolation suite requires disposable PostgreSQL",
    ),
]

TENANT_A = UUID("10000000-0000-4000-8000-000000000001")
TENANT_B = UUID("10000000-0000-4000-8000-000000000002")
USER_A = UUID("20000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
MULTI = UUID("20000000-0000-4000-8000-000000000003")


def _engine(name: str, **kwargs: object) -> Engine:
    return create_engine(os.environ[name], **kwargs)


@pytest.fixture(scope="module", autouse=True)
def synthetic_fixtures() -> None:
    now = datetime.now(UTC)
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE audit_events, tenant_isolation_probes, application_sessions, "
                "memberships, "
                "external_identities, users, tenants CASCADE"
            )
        )
        for tenant_id, name in ((TENANT_A, "Tenant A"), (TENANT_B, "Tenant B")):
            connection.execute(
                text("INSERT INTO tenants VALUES (:id, :name, :slug, 'active', :now, :now)"),
                {
                    "id": tenant_id,
                    "name": name,
                    "slug": name.lower().replace(" ", "-"),
                    "now": now,
                },
            )
        for user_id, name in ((USER_A, "User A"), (USER_B, "User B"), (MULTI, "Multi User")):
            connection.execute(
                text(
                    "INSERT INTO users (id, display_name, status, created_at) "
                    "VALUES (:id, :name, 'active', :now)"
                ),
                {"id": user_id, "name": name, "now": now},
            )
        for tenant_id, user_id, role in (
            (TENANT_A, USER_A, "owner"),
            (TENANT_B, USER_B, "auditor"),
            (TENANT_A, MULTI, "member"),
            (TENANT_B, MULTI, "member"),
        ):
            connection.execute(
                text("INSERT INTO memberships VALUES (:id, :tenant, :user, :role, 'active', :now)"),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "user": user_id,
                    "role": role,
                    "now": now,
                },
            )
        for tenant_id, user_id, role, name in (
            (TENANT_A, USER_A, "owner", "User A"),
            (TENANT_B, USER_B, "auditor", "User B"),
        ):
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, tenant_id, actor_user_id, actor_display_name, actor_role, "
                    "action, resource_type, request_id, schema_version, changed_fields, "
                    "new_values, metadata) "
                    "VALUES (:id, :tenant, :user, :name, :role, 'auth.tenant_selected', "
                    "'application_session', :request, 1, '[]'::jsonb, "
                    "'{\"selected\": true}'::jsonb, '{}'::jsonb)"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "user": user_id,
                    "name": name,
                    "role": role,
                    "request": uuid4(),
                },
            )
        for tenant_id, value in ((TENANT_A, "A protected"), (TENANT_B, "B protected")):
            connection.execute(
                text("INSERT INTO tenant_isolation_probes VALUES (:id, :tenant, :value, :now)"),
                {"id": uuid4(), "tenant": tenant_id, "value": value, "now": now},
            )


def _context(connection: Connection, user: UUID, tenant: UUID) -> None:
    connection.execute(text("SELECT set_config('app.user_id', :user, true)"), {"user": str(user)})
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
    )


def _values(user: UUID, tenant: UUID) -> list[str]:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        _context(connection, user, tenant)
        return list(
            connection.execute(
                text("SELECT value FROM tenant_isolation_probes ORDER BY value")
            ).scalars()
        )


def test_runtime_role_is_unprivileged_and_not_table_owner() -> None:
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = 'pmcloud_app'"
            )
        ).one()
        owners = (
            connection.execute(
                text(
                    "SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename IN ('tenants', 'memberships', 'tenant_isolation_probes')"
                )
            )
            .scalars()
            .all()
        )
    assert tuple(role) == (False, False, False, False, False)
    assert owners == ["pmcloud_migrator"]


def test_cross_tenant_reads_and_unsafe_unfiltered_query_are_denied() -> None:
    assert _values(USER_A, TENANT_A) == ["A protected"]
    assert _values(USER_A, TENANT_B) == []
    assert _values(USER_B, TENANT_A) == []
    assert _values(USER_B, TENANT_B) == ["B protected"]
    assert _values(MULTI, TENANT_A) == ["A protected"]
    assert _values(MULTI, TENANT_B) == ["B protected"]


def _audit_values(user: UUID, tenant: UUID) -> list[UUID]:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        _context(connection, user, tenant)
        return list(connection.execute(text("SELECT id FROM audit_events ORDER BY id")).scalars())


def test_audit_reader_roles_and_tenant_isolation() -> None:
    assert len(_audit_values(USER_A, TENANT_A)) == 1
    assert _audit_values(USER_A, TENANT_B) == []
    assert _audit_values(USER_B, TENANT_A) == []
    assert len(_audit_values(USER_B, TENANT_B)) == 1
    assert _audit_values(MULTI, TENANT_A) == []


def test_audit_runtime_insert_rejects_cross_tenant_and_actor_forgery() -> None:
    attempts = [
        {"tenant": TENANT_B, "user": USER_A, "name": "User A", "role": "owner"},
        {"tenant": TENANT_A, "user": USER_B, "name": "User A", "role": "owner"},
        {"tenant": TENANT_A, "user": USER_A, "name": "Forged", "role": "owner"},
        {"tenant": TENANT_A, "user": USER_A, "name": "User A", "role": "admin"},
    ]
    for attempt in attempts:
        with _engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            transaction = connection.begin()
            _context(connection, USER_A, TENANT_A)
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "INSERT INTO audit_events "
                        "(id, tenant_id, actor_user_id, actor_display_name, actor_role, action, "
                        "resource_type, request_id, schema_version, changed_fields, metadata) "
                        "VALUES (:id, :tenant, :user, :name, :role, 'auth.tenant_selected', "
                        "'application_session', :request, 1, '[]'::jsonb, '{}'::jsonb)"
                    ),
                    {**attempt, "id": uuid4(), "request": uuid4()},
                )
            transaction.rollback()


def test_audit_runtime_update_delete_are_denied() -> None:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        _context(connection, USER_A, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text("UPDATE audit_events SET action = 'auth.tenant_selected'"))
        connection.rollback()
        with pytest.raises(DBAPIError):
            connection.execute(text("DELETE FROM audit_events"))
        connection.rollback()


def test_cross_tenant_insert_is_denied() -> None:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        _context(connection, USER_A, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text("INSERT INTO tenant_isolation_probes VALUES (:id, :tenant, 'denied', :now)"),
                {"id": uuid4(), "tenant": TENANT_B, "now": datetime.now(UTC)},
            )
        transaction.rollback()


def test_cross_tenant_update_and_delete_affect_no_rows() -> None:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        _context(connection, USER_A, TENANT_A)
        updated = connection.execute(
            text(
                "UPDATE tenant_isolation_probes SET value = 'compromised' WHERE tenant_id = :tenant"
            ),
            {"tenant": TENANT_B},
        )
        deleted = connection.execute(
            text("DELETE FROM tenant_isolation_probes WHERE tenant_id = :tenant"),
            {"tenant": TENANT_B},
        )
        assert updated.rowcount == 0
        assert deleted.rowcount == 0
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        assert (
            connection.scalar(
                text("SELECT value FROM tenant_isolation_probes WHERE tenant_id = :tenant"),
                {"tenant": TENANT_B},
            )
            == "B protected"
        )


def test_transaction_local_context_does_not_leak_through_pool() -> None:
    engine = _engine("PMC_TEST_RUNTIME_DATABASE_URL", pool_size=1, max_overflow=0)
    with engine.begin() as connection:
        _context(connection, USER_A, TENANT_A)
        assert connection.scalar(text("SELECT count(*) FROM tenant_isolation_probes")) == 1
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM tenant_isolation_probes")) == 0
        _context(connection, USER_B, TENANT_B)
        assert connection.scalar(text("SELECT count(*) FROM tenant_isolation_probes")) == 1


def test_membership_revocation_removes_existing_context_access() -> None:
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'revoked' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )
    assert _values(USER_A, TENANT_A) == []
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'active' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )


def test_runtime_cannot_self_elevate_membership_role() -> None:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        transaction = connection.begin()
        _context(connection, USER_A, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE memberships SET role = 'owner' WHERE tenant_id = :tenant"),
                {"tenant": TENANT_A},
            )
        transaction.rollback()


def test_raw_session_token_is_not_stored() -> None:
    raw = "synthetic-session-token-that-is-not-persisted"
    digest = hashlib.sha256(raw.encode()).digest()
    now = datetime.now(UTC)
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO application_sessions VALUES "
                "(:id, :user, :hash, :tenant, :csrf, :now, :expires, :now, NULL)"
            ),
            {
                "id": uuid4(),
                "user": USER_A,
                "hash": digest,
                "tenant": TENANT_A,
                "csrf": hashlib.sha256(b"csrf").digest(),
                "now": now,
                "expires": now + timedelta(hours=1),
            },
        )
        stored = connection.scalar(
            text("SELECT token_hash FROM application_sessions WHERE user_id = :user"),
            {"user": USER_A},
        )
    assert stored == digest
    assert raw.encode() != stored


def _application_session(
    user_id: UUID,
    tenant_id: UUID | None,
    *,
    expired: bool = False,
    revoked: bool = False,
) -> tuple[str, str]:
    raw = generate_token()
    csrf = generate_token()
    now = datetime.now(UTC)
    expires = now - timedelta(minutes=1) if expired else now + timedelta(hours=1)
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO application_sessions VALUES "
                "(:id, :user, :hash, :tenant, :csrf, :now, :expires, :now, :revoked)"
            ),
            {
                "id": uuid4(),
                "user": user_id,
                "hash": token_hash(raw),
                "tenant": tenant_id,
                "csrf": token_hash(csrf),
                "now": now,
                "expires": expires,
                "revoked": now if revoked else None,
            },
        )
    return raw, csrf


def _client(raw: str | None = None, csrf: str | None = None) -> TestClient:
    client = TestClient(app)
    if raw:
        client.cookies.set("pm_session", raw)
    if csrf:
        client.cookies.set("pm_csrf", csrf)
    return client


def _set_session_tenant_as_runtime(raw: str, user_id: UUID, tenant_id: UUID) -> int:
    with _engine("PMC_TEST_RUNTIME_DATABASE_URL").begin() as connection:
        connection.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(user_id)}
        )
        connection.execute(
            text("SELECT set_config('app.session_hash', :session, true)"),
            {"session": token_hash(raw).hex()},
        )
        result = connection.execute(
            text(
                "UPDATE application_sessions SET current_tenant_id = :tenant "
                "WHERE token_hash = :session"
            ),
            {"tenant": tenant_id, "session": token_hash(raw)},
        )
        return result.rowcount


def test_session_matrix_accepts_only_active_session() -> None:
    active, csrf = _application_session(USER_A, TENANT_A)
    assert _client(active, csrf).get("/auth/me").status_code == 200
    assert _client().get("/auth/me").status_code == 401
    assert _client(generate_token()).get("/auth/me").status_code == 401
    expired, _ = _application_session(USER_A, TENANT_A, expired=True)
    assert _client(expired).get("/auth/me").status_code == 401
    revoked, _ = _application_session(USER_A, TENANT_A, revoked=True)
    assert _client(revoked).get("/auth/me").status_code == 401


def test_csrf_matrix_on_mutating_endpoint() -> None:
    raw, csrf = _application_session(USER_A, TENANT_A)
    client = _client(raw, csrf)
    payload = {"tenant_id": str(TENANT_A)}
    assert client.post("/auth/tenant", json=payload).status_code == 403
    assert (
        client.post(
            "/auth/tenant",
            json=payload,
            headers={"X-CSRF-Token": generate_token()},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/auth/tenant",
            json=payload,
            headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:3000"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("user_id", "tenant_id", "expected"),
    [
        (USER_A, TENANT_A, 200),
        (USER_A, TENANT_B, 403),
        (USER_B, TENANT_A, 403),
        (MULTI, TENANT_A, 200),
        (MULTI, TENANT_B, 200),
    ],
)
def test_tenant_selection_requires_active_membership(
    user_id: UUID, tenant_id: UUID, expected: int
) -> None:
    raw, csrf = _application_session(user_id, None)
    response = _client(raw, csrf).post(
        "/auth/tenant",
        json={"tenant_id": str(tenant_id)},
        headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:3000"},
    )
    assert response.status_code == expected


def test_tenant_selection_audit_uses_server_request_id() -> None:
    raw, csrf = _application_session(USER_A, None)
    response = _client(raw, csrf).post(
        "/auth/tenant",
        json={"tenant_id": str(TENANT_A)},
        headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:3000"},
    )
    assert response.status_code == 200
    request_id = UUID(response.headers["X-Request-ID"])
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE request_id = :request "
                    "AND action = 'auth.tenant_selected' AND tenant_id = :tenant"
                ),
                {"request": request_id, "tenant": TENANT_A},
            )
            == 1
        )


def test_audit_failure_rolls_back_tenant_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, csrf = _application_session(USER_A, None)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr("pmc_api.auth.record", fail)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/auth/tenant",
        json={"tenant_id": str(TENANT_A)},
        cookies={"pm_session": raw, "pm_csrf": csrf},
        headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:3000"},
    )
    assert response.status_code == 500
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        assert (
            connection.scalar(
                text("SELECT current_tenant_id FROM application_sessions WHERE token_hash = :hash"),
                {"hash": token_hash(raw)},
            )
            is None
        )


def test_database_enforces_session_current_tenant_membership() -> None:
    user_a_session, _ = _application_session(USER_A, None)
    assert _set_session_tenant_as_runtime(user_a_session, USER_A, TENANT_A) == 1

    denied_session, _ = _application_session(USER_A, None)
    with pytest.raises(DBAPIError):
        _set_session_tenant_as_runtime(denied_session, USER_A, TENANT_B)

    multi_session, _ = _application_session(MULTI, None)
    assert _set_session_tenant_as_runtime(multi_session, MULTI, TENANT_A) == 1
    assert _set_session_tenant_as_runtime(multi_session, MULTI, TENANT_B) == 1


def test_database_denies_revoked_membership_as_session_tenant() -> None:
    raw, _ = _application_session(USER_A, None)
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'revoked' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )
    try:
        with pytest.raises(DBAPIError):
            _set_session_tenant_as_runtime(raw, USER_A, TENANT_A)
    finally:
        with admin.begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status = 'active' "
                    "WHERE tenant_id = :tenant AND user_id = :user"
                ),
                {"tenant": TENANT_A, "user": USER_A},
            )


def test_existing_session_loses_tenant_after_membership_revocation() -> None:
    raw, csrf = _application_session(USER_A, TENANT_A)
    client = _client(raw, csrf)
    assert client.get("/tenant/context").status_code == 200
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'revoked' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )
    assert client.get("/tenant/context").status_code == 403
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'active' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )


def test_revoked_membership_session_can_still_log_out() -> None:
    raw, csrf = _application_session(USER_A, TENANT_A)
    admin = _engine("PMC_TEST_ADMIN_DATABASE_URL")
    with admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE memberships SET status = 'revoked' "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {"tenant": TENANT_A, "user": USER_A},
        )
    try:
        response = _client(raw, csrf).post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:3000"},
        )
        assert response.status_code == 204
        with admin.connect() as connection:
            current_tenant_id, revoked_at = connection.execute(
                text(
                    "SELECT current_tenant_id, revoked_at FROM application_sessions "
                    "WHERE token_hash = :session"
                ),
                {"session": token_hash(raw)},
            ).one()
        assert current_tenant_id is None
        assert revoked_at is not None
    finally:
        with admin.begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status = 'active' "
                    "WHERE tenant_id = :tenant AND user_id = :user"
                ),
                {"tenant": TENANT_A, "user": USER_A},
            )


def _login_transaction(*, expired: bool = False, used: bool = False) -> tuple[str, str]:
    raw_state = generate_token()
    raw_binding = generate_token()
    now = datetime.now(UTC)
    expires = now - timedelta(minutes=1) if expired else now + timedelta(minutes=5)
    encrypted = TransactionCipher(os.environ["PMC_LOGIN_TRANSACTION_KEY"]).encrypt(
        "synthetic-pkce-verifier"
    )
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO oidc_login_transactions "
                "(id, state_hash, login_binding_hash, encrypted_pkce_verifier, nonce, "
                "created_at, expires_at, used_at) VALUES "
                "(:id, :state, :binding, :verifier, :nonce, :now, :expires, :used)"
            ),
            {
                "id": uuid4(),
                "state": token_hash(raw_state),
                "binding": token_hash(raw_binding),
                "verifier": encrypted,
                "nonce": "synthetic-nonce",
                "now": now,
                "expires": expires,
                "used": now if used else None,
            },
        )
    return raw_state, raw_binding


def _set_login_binding(client: TestClient, binding: str) -> None:
    client.cookies.set("pm_login", binding, path="/auth")


def test_invalid_expired_and_previously_used_state_are_denied() -> None:
    client = _client()
    assert (
        client.get("/auth/callback", params={"code": "x", "state": generate_token()}).status_code
        == 400
    )
    expired, expired_binding = _login_transaction(expired=True)
    _set_login_binding(client, expired_binding)
    assert client.get("/auth/callback", params={"code": "x", "state": expired}).status_code == 400
    used, used_binding = _login_transaction(used=True)
    _set_login_binding(client, used_binding)
    assert client.get("/auth/callback", params={"code": "x", "state": used}).status_code == 400


def test_valid_callback_rotates_session_and_state_cannot_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_value, login_binding = _login_transaction()
    upstream_token = generate_token()

    async def exchange(_self: OIDCProvider, *, code: str, verifier: str) -> str:
        assert code == "synthetic-code"
        assert verifier == "synthetic-pkce-verifier"
        return upstream_token

    async def validate(_self: OIDCProvider, encoded_token: str, *, nonce: str) -> IdentityClaims:
        assert encoded_token == upstream_token
        assert nonce == "synthetic-nonce"
        return IdentityClaims(
            issuer="https://issuer.example/realms/perfect-match",
            subject="synthetic-callback-subject",
            display_name="Synthetic callback user",
            email="callback-user@example.test",
        )

    monkeypatch.setattr(OIDCProvider, "exchange_code", exchange)
    monkeypatch.setattr(OIDCProvider, "validate_id_token", validate)
    client = _client()
    _set_login_binding(client, login_binding)
    response = client.get(
        "/auth/callback",
        params={"code": "synthetic-code", "state": state_value},
        follow_redirects=False,
    )
    assert response.status_code == 303
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "pm_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        for cookie in cookies
    )
    assert all(upstream_token not in cookie for cookie in cookies)
    assert any("pm_login=" in cookie and "Max-Age=0" in cookie for cookie in cookies)
    _set_login_binding(client, login_binding)
    replay = client.get(
        "/auth/callback",
        params={"code": "synthetic-code", "state": state_value},
        follow_redirects=False,
    )
    assert replay.status_code == 400


def test_cross_browser_callback_requires_initiating_browser_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_token = generate_token()

    async def authorization_url(
        _self: OIDCProvider, *, state: str, nonce: str, challenge: str
    ) -> str:
        assert nonce
        assert challenge
        return f"https://issuer.example/authorize?state={state}"

    async def exchange(_self: OIDCProvider, *, code: str, verifier: str) -> str:
        assert code == "synthetic-code"
        assert verifier
        return upstream_token

    async def validate(_self: OIDCProvider, encoded_token: str, *, nonce: str) -> IdentityClaims:
        assert encoded_token == upstream_token
        assert nonce
        return IdentityClaims(
            issuer="https://issuer.example/realms/perfect-match",
            subject="synthetic-cross-browser-subject",
            display_name="Synthetic cross browser user",
            email="cross-browser@example.test",
        )

    monkeypatch.setattr(OIDCProvider, "authorization_url", authorization_url)
    monkeypatch.setattr(OIDCProvider, "exchange_code", exchange)
    monkeypatch.setattr(OIDCProvider, "validate_id_token", validate)

    browser_a = _client()
    login = browser_a.get("/auth/login", follow_redirects=False)
    assert login.status_code == 303
    login_cookies = login.headers.get_list("set-cookie")
    assert any(
        "pm_login=" in cookie
        and "HttpOnly" in cookie
        and "SameSite=lax" in cookie
        and "Path=/auth" in cookie
        and "Max-Age=300" in cookie
        for cookie in login_cookies
    )
    state_value = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    raw_binding = browser_a.cookies.get("pm_login")
    assert raw_binding is not None

    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        stored_binding = connection.scalar(
            text(
                "SELECT login_binding_hash FROM oidc_login_transactions WHERE state_hash = :state"
            ),
            {"state": token_hash(state_value)},
        )
    assert stored_binding == token_hash(raw_binding)
    assert raw_binding.encode() != stored_binding

    browser_b = _client()
    swapped = browser_b.get(
        "/auth/callback",
        params={"code": "synthetic-code", "state": state_value},
        follow_redirects=False,
    )
    assert swapped.status_code == 400
    assert "pm_session" not in swapped.cookies

    _set_login_binding(browser_b, generate_token())
    wrong = browser_b.get(
        "/auth/callback",
        params={"code": "synthetic-code", "state": state_value},
        follow_redirects=False,
    )
    assert wrong.status_code == 400
    assert "pm_session" not in wrong.cookies

    completed = browser_a.get(
        "/auth/callback",
        params={"code": "synthetic-code", "state": state_value},
        follow_redirects=False,
    )
    assert completed.status_code == 303
    assert browser_a.cookies.get("pm_session") is not None
