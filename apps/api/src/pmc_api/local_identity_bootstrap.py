from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import create_engine, text

REALM = "perfect-match"
TENANT_A = UUID("10000000-0000-4000-8000-000000000001")
TENANT_B = UUID("10000000-0000-4000-8000-000000000002")
USER_A = UUID("20000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
MULTI_USER = UUID("20000000-0000-4000-8000-000000000003")


def _request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def _ensure_user(client: httpx.Client, username: str, email: str, password: str) -> str:
    representation = {
        "username": username,
        "email": email,
        "firstName": username,
        "lastName": "Synthetic",
        "enabled": True,
        "emailVerified": True,
        "requiredActions": [],
    }
    users = _request(
        client, "GET", f"admin/realms/{REALM}/users", params={"username": username, "exact": "true"}
    ).json()
    if users:
        user_id = str(users[0]["id"])
        _request(
            client,
            "PUT",
            f"admin/realms/{REALM}/users/{user_id}",
            json=representation,
        )
    else:
        response = _request(
            client,
            "POST",
            f"admin/realms/{REALM}/users",
            json=representation,
        )
        user_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    _request(
        client,
        "PUT",
        f"admin/realms/{REALM}/users/{user_id}/reset-password",
        json={"type": "password", "value": password, "temporary": False},
    )
    return user_id


def _configure_keycloak() -> dict[UUID, tuple[str, str, str]]:
    base_url = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/")
    with httpx.Client(base_url=base_url, timeout=20) as anonymous:
        token = _request(
            anonymous,
            "POST",
            "realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": os.environ["KEYCLOAK_ADMIN"],
                "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
            },
        ).json()["access_token"]
    with httpx.Client(
        base_url=base_url,
        timeout=20,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        realm = client.get(f"admin/realms/{REALM}")
        if realm.status_code == 404:
            _request(client, "POST", "admin/realms", json={"realm": REALM, "enabled": True})
        else:
            realm.raise_for_status()

        client_id = os.environ.get("OIDC_CLIENT_ID", "perfect-match-web")
        clients = _request(
            client,
            "GET",
            f"admin/realms/{REALM}/clients",
            params={"clientId": client_id},
        ).json()
        representation = {
            "clientId": client_id,
            "name": "Perfect Match local web",
            "enabled": True,
            "publicClient": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": [os.environ["OIDC_CALLBACK_URL"]],
            "webOrigins": [os.environ["PMC_WEB_URL"]],
            "attributes": {"pkce.code.challenge.method": "S256"},
        }
        if clients:
            _request(
                client,
                "PUT",
                f"admin/realms/{REALM}/clients/{clients[0]['id']}",
                json=representation,
            )
        else:
            _request(client, "POST", f"admin/realms/{REALM}/clients", json=representation)

        definitions = (
            (
                USER_A,
                "pmc-user-a",
                "pmc-user-a@example.test",
                os.environ["KEYCLOAK_USER_A_PASSWORD"],
            ),
            (
                USER_B,
                "pmc-user-b",
                "pmc-user-b@example.test",
                os.environ["KEYCLOAK_USER_B_PASSWORD"],
            ),
            (
                MULTI_USER,
                "pmc-multi-user",
                "pmc-multi-user@example.test",
                os.environ["KEYCLOAK_MULTI_USER_PASSWORD"],
            ),
        )
        return {
            app_id: (username, email, _ensure_user(client, username, email, password))
            for app_id, username, email, password in definitions
        }


def _seed_application(subjects: dict[UUID, tuple[str, str, str]]) -> None:
    now = datetime.now(UTC)
    issuer = os.environ["OIDC_ISSUER"]
    engine = create_engine(os.environ["PMC_DATABASE_ADMIN_URL"])
    with engine.begin() as connection:
        for tenant_id, name, slug in (
            (TENANT_A, "Tenant A", "tenant-a"),
            (TENANT_B, "Tenant B", "tenant-b"),
        ):
            connection.execute(
                text(
                    """INSERT INTO tenants (id, name, slug, status, created_at, updated_at)
                    VALUES (:id, :name, :slug, 'active', :now, :now)
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug,
                    status = 'active', updated_at = EXCLUDED.updated_at"""
                ),
                {"id": tenant_id, "name": name, "slug": slug, "now": now},
            )
        for user_id, (username, email, subject) in subjects.items():
            connection.execute(
                text(
                    """INSERT INTO users (id, display_name, email, status, created_at)
                    VALUES (:id, :name, :email, 'active', :now)
                    ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name,
                    email = EXCLUDED.email, status = 'active'"""
                ),
                {"id": user_id, "name": username, "email": email, "now": now},
            )
            connection.execute(
                text(
                    """INSERT INTO external_identities (id, user_id, issuer, subject, created_at)
                    VALUES (gen_random_uuid(), :user_id, :issuer, :subject, :now)
                    ON CONFLICT (issuer, subject) DO UPDATE SET user_id = EXCLUDED.user_id"""
                ),
                {"user_id": user_id, "issuer": issuer, "subject": subject, "now": now},
            )
        memberships = (
            (TENANT_A, USER_A, "member"),
            (TENANT_B, USER_B, "member"),
            (TENANT_A, MULTI_USER, "member"),
            (TENANT_B, MULTI_USER, "auditor"),
        )
        for tenant_id, user_id, role in memberships:
            connection.execute(
                text(
                    """INSERT INTO memberships
                    (id, tenant_id, user_id, role, status, created_at)
                    VALUES (gen_random_uuid(), :tenant, :user, :role, 'active', :now)
                    ON CONFLICT (tenant_id, user_id) DO UPDATE
                    SET role = EXCLUDED.role, status = 'active'"""
                ),
                {"tenant": tenant_id, "user": user_id, "role": role, "now": now},
            )


def main() -> None:
    _seed_application(_configure_keycloak())


if __name__ == "__main__":
    main()
