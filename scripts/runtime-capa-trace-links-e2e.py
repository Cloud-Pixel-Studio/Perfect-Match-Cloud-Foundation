"""Validate CAPA 0039 direct control traceability through OIDC and the web proxy."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from runpy import run_path

import httpx
from dotenv import dotenv_values

_identity = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API, WEB = _identity["API"], _identity["WEB"]
login, csrf, select_tenant = (
    _identity[name] for name in ("login", "csrf", "select_tenant")
)
phase = "startup"


def checked(response: httpx.Response, status: int = 200) -> object:
    if response.status_code != status:
        raise AssertionError(f"unexpected HTTP status {response.status_code}")
    return response.json()


def row_with_code(rows: object, code: str) -> dict[str, object]:
    if not isinstance(rows, list):
        raise TypeError("expected a record list")
    return next(row for row in rows if row.get("code") == code)


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("CAPA trace validation requires local development")
    with ExitStack() as stack:
        owner, author = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(2)
        )
        clients = (owner, author)
        try:
            phase = "OIDC login and tenant selection"
            for client, username, key in (
                (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
                (author, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
            ):
                login(client, username, str(env[key]))
                select_tenant(client)

            phase = "demo scope lookup"
            units = checked(author.get(f"{API}/organization/units?limit=100"))
            unit = row_with_code(units, "DEV-ACCESS-UI")
            capas = checked(
                author.get(
                    f"{API}/capas",
                    params={"unit_id": unit["id"], "q": "DEMO-CAPA-001"},
                )
            )
            capa = row_with_code(capas, "DEMO-CAPA-001")
            instances = checked(
                author.get(
                    f"{API}/control-instances",
                    params={"unit_id": unit["id"], "search": "DEMO-IMP-001"},
                )
            )
            instance = row_with_code(instances, "DEMO-IMP-001")

            phase = "direct link snapshot and web proxy"
            links = checked(author.get(f"{API}/capas/{capa['id']}/control-links"))
            if not isinstance(links, list):
                raise TypeError("expected CAPA control link list")
            active = [
                row
                for row in links
                if row["control_instance_id"] == instance["id"]
                and row["status"] == "active"
            ]
            if len(active) != 1:
                raise AssertionError("expected one active idempotent demo control link")
            link = active[0]
            if (
                link["snapshot_code"] != "DEMO-IMP-001"
                or link["snapshot_name"] != instance["name"]
                or link["linked_target_version"] != instance["row_version"]
            ):
                raise AssertionError("direct traceability snapshot is incomplete")
            proxied = checked(
                author.get(f"{WEB}/api/identity/capas/{capa['id']}/control-links")
            )
            if not isinstance(proxied, list) or not any(
                row["id"] == link["id"] for row in proxied
            ):
                raise AssertionError("web proxy omitted direct CAPA traceability")

            phase = "authority and optimistic concurrency"
            if owner.get(f"{API}/capas/{capa['id']}/control-links").status_code not in {
                403,
                404,
            }:
                raise AssertionError(
                    "tenant owner received implicit QMS trace authority"
                )
            stale = author.post(
                f"{API}/capas/{capa['id']}/control-links",
                json={
                    "expected_version": 1,
                    "control_instance_id": instance["id"],
                },
                headers=csrf(author),
            )
            if stale.status_code != 409:
                raise AssertionError("stale CAPA trace mutation was accepted")
        finally:
            for client in clients:
                if "pm_csrf" in client.cookies:
                    client.post(f"{API}/auth/logout", headers=csrf(client))
    print("OIDC, CAPA 0039 snapshot, authority, version guard and web proxy: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- keep credentials and tokens redacted.
        raise SystemExit(
            f"CAPA trace validation failed during {phase}: {type(error).__name__}"
        ) from None
