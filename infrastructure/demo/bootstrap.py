"""Initial synthetic identities for the isolated VM demo; never a production installer."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import httpx
from pmc_api import local_identity_bootstrap as identity
from sqlalchemy import Connection, create_engine, text


def existing_demo_complete(connection: Connection, issuer: str) -> bool:
    """Check persisted structural completion without resetting edited accounts."""
    for index in range(1, 7):
        user = f"20000000-0000-4000-8000-{index:012}"
        found = connection.scalar(
            text(
                "SELECT count(*) FROM users u JOIN external_identities e "
                "ON e.user_id = u.id WHERE u.id = :user AND e.issuer = :issuer"
            ),
            {"user": user, "issuer": issuer},
        )
        if found != 1:
            return False
    for tenant, user in (
        (identity.TENANT_A, identity.OWNER_USER),
        (identity.TENANT_A, identity.USER_A),
        (identity.TENANT_B, identity.USER_B),
        (identity.TENANT_A, identity.MULTI_USER),
        (identity.TENANT_B, identity.MULTI_USER),
        (identity.TENANT_B, UUID("20000000-0000-4000-8000-000000000005")),
        (identity.TENANT_B, UUID("20000000-0000-4000-8000-000000000006")),
    ):
        found = connection.scalar(
            text(
                "SELECT count(*) FROM memberships "
                "WHERE tenant_id = :tenant AND user_id = :user"
            ),
            {
                "tenant": str(tenant),
                "user": str(user),
            },
        )
        if found != 1:
            return False
    return True


def main() -> None:
    if (
        os.environ.get("PMC_ENVIRONMENT") != "development"
        or os.environ.get("POSTGRES_DB") != "pmqms_demo"
        or os.environ.get("DEMO_ORIGIN") != "https://demo.3-238-70-198.sslip.io"
    ):
        raise RuntimeError("refusing bootstrap outside the approved synthetic demo")
    engine = create_engine(os.environ["PMC_DATABASE_ADMIN_URL"])
    with engine.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM users"))
        if count:
            # Existing accounts/roles/passwords must never be reset by a restart.
            if not existing_demo_complete(connection, os.environ["OIDC_ISSUER"]):
                raise RuntimeError("partial demo bootstrap requires recovery review")
            print("Existing demo preserved; no identity or membership reset.")
            return

    subjects = identity._configure_keycloak()
    with httpx.Client(base_url="http://keycloak:8080/", timeout=30) as client:
        response = client.post(
            "realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": os.environ["KEYCLOAK_ADMIN"],
                "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
            },
        )
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        for user_id, username, key in (
            (
                UUID("20000000-0000-4000-8000-000000000005"),
                "pmc-company-b-owner",
                "KEYCLOAK_B_OWNER_PASSWORD",
            ),
            (
                UUID("20000000-0000-4000-8000-000000000006"),
                "pmc-company-b-reviewer",
                "KEYCLOAK_B_REVIEWER_PASSWORD",
            ),
        ):
            email = username + "@example.test"
            subject = identity._ensure_user(client, username, email, os.environ[key])
            subjects[user_id] = (username, email, subject)
    identity._seed_application(subjects)
    with engine.begin() as connection:
        for user_id, role in (
            (UUID("20000000-0000-4000-8000-000000000005"), "owner"),
            (UUID("20000000-0000-4000-8000-000000000006"), "member"),
        ):
            connection.execute(
                text(
                    """INSERT INTO memberships
                    (id, tenant_id, user_id, role, status, created_at)
                    VALUES (gen_random_uuid(), :tenant, :user, :role, 'active', :now)"""
                ),
                {
                    "tenant": identity.TENANT_B,
                    "user": user_id,
                    "role": role,
                    "now": datetime.now(UTC),
                },
            )
        for tenant_id, name in (
            (identity.TENANT_A, "Perfect Match Industries · DEMO"),
            (identity.TENANT_B, "Cloud Pixel Manufacturing · DEMO"),
        ):
            connection.execute(
                text("UPDATE tenants SET name = :name WHERE id = :id"),
                {"name": name, "id": tenant_id},
            )
    print(
        "Six synthetic accounts and two independent demonstration companies initialized."
    )


if __name__ == "__main__":
    main()
