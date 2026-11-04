"""Exercise risk review through local OIDC, API, audit and web proxy."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from runpy import run_path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

# Reuse the established local-only OIDC helpers without running that script's main.
_identity = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API, WEB = _identity["API"], _identity["WEB"]
login, csrf, select_tenant, post = (
    _identity[name] for name in ("login", "csrf", "select_tenant", "post")
)
phase = "startup"


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("risk E2E requires local development environment")
    grant_ids: list[str] = []
    cleanup_failed = False
    with ExitStack() as stack:
        owner, author, reviewer = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(3)
        )
        clients = (owner, author, reviewer)
        try:
            phase = "OIDC login and tenant selection"
            for client, username, key in (
                (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
                (author, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
                (reviewer, "pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
            ):
                login(client, username, str(env[key]))
                select_tenant(client)
            members = owner.get(f"{API}/organization/members?limit=100").json()
            users = {
                prefix: next(
                    r["id"] for r in members if r["display_name"].startswith(prefix)
                )
                for prefix in ("pmc-user-a", "pmc-multi-user")
            }
            unit = next(
                r
                for r in owner.get(f"{API}/organization/units?limit=100").json()
                if r["code"] == "DEV-ACCESS-UI" and r["status"] == "active"
            )
            existing = {
                (r["user_id"], r["unit_id"], r["capability"])
                for r in owner.get(f"{API}/qms-access/grants").json()
                if r["status"] == "active"
            }
            phase = "temporary explicit capabilities"
            for prefix, capabilities in (
                ("pmc-user-a", ("processes.read", "risks.read", "risks.manage")),
                ("pmc-multi-user", ("risks.read", "risks.review")),
            ):
                for capability in capabilities:
                    if (users[prefix], unit["id"], capability) in existing:
                        continue
                    response = post(
                        owner,
                        f"{API}/qms-access/grants",
                        {
                            "user_id": users[prefix],
                            "unit_id": unit["id"],
                            "capability": capability,
                        },
                    )
                    if response.status_code != 201:
                        raise AssertionError("temporary risk capability rejected")
                    grant_ids.append(response.json()["id"])
            processes = author.get(
                f"{API}/processes", params={"unit_id": unit["id"], "limit": 50}
            ).json()
            process = next(r for r in processes if r["status"] == "active")
            code = f"DEV-E2E-RISK-{uuid4().hex[:10].upper()}"
            phase = "risk creation and computed scoring"
            response = post(
                author,
                f"{API}/risks",
                {
                    "unit_id": unit["id"],
                    "process_id": process["id"],
                    "code": code,
                    "name": "Development continuity risk",
                    "risk_type": "risk",
                    "category": "process",
                    "description": "Fictional local workflow interruption for validation.",
                    "likelihood": 4,
                    "impact": 5,
                    "residual_likelihood": 2,
                    "residual_impact": 3,
                    "response_strategy": "mitigate",
                    "mitigation_plan": "Exercise the response workflow.",
                },
            )
            if response.status_code != 201:
                raise AssertionError("risk could not be created")
            risk = response.json()
            if (
                risk["initial_score"],
                risk["initial_level"],
                risk["residual_score"],
                risk["residual_level"],
            ) != (20, "critical", 6, "moderate"):
                raise AssertionError("risk scoring was incorrect")
            phase = "separate author and review permissions"
            denied = post(
                author,
                f"{API}/risks/{risk['id']}/transition",
                {
                    "expected_version": risk["row_version"],
                    "target_state": "assessed",
                    "decision": "Denied author review",
                },
            )
            if denied.status_code != 403:
                raise AssertionError("author received review authority without grant")
            if (
                owner.get(f"{API}/risks", params={"unit_id": unit["id"]}).status_code
                != 403
            ):
                raise AssertionError(
                    "tenant owner received implicit QMS risk read access"
                )
            phase = "controlled assessment and monitoring"
            for target in ("assessed", "monitoring"):
                response = post(
                    reviewer,
                    f"{API}/risks/{risk['id']}/transition",
                    {
                        "expected_version": risk["row_version"],
                        "target_state": target,
                        "decision": "Development review accepted",
                    },
                )
                if response.status_code != 200:
                    raise AssertionError("risk workflow transition failed")
                risk = response.json()
            stale = author.patch(
                f"{API}/risks/{risk['id']}",
                json={"expected_version": 1, "name": "Stale edit"},
                headers=csrf(author),
            )
            if stale.status_code != 409:
                raise AssertionError("risk stale update was not rejected")
            phase = "same-origin risk proxy"
            proxy = author.get(
                f"{WEB}/api/identity/risks", params={"unit_id": unit["id"], "q": code}
            )
            if proxy.status_code != 200 or not any(
                r["id"] == risk["id"] for r in proxy.json()
            ):
                raise AssertionError("risk web proxy did not return scoped record")
            phase = "controlled closure and audit"
            response = post(
                reviewer,
                f"{API}/risks/{risk['id']}/transition",
                {
                    "expected_version": risk["row_version"],
                    "target_state": "closed",
                    "decision": "Development record closed",
                    "closure_notes": "Fictional local exercise completed; no operational risk remains.",
                },
            )
            if response.status_code != 200 or response.json()["state"] != "closed":
                raise AssertionError("risk closure failed")
            events = owner.get(f"{API}/audit/events?limit=100").json()["items"]
            actions = {r["action"] for r in events if r["resource_id"] == risk["id"]}
            if not {"risk.created", "risk.transitioned"} <= actions:
                raise AssertionError("risk audit history incomplete")
        finally:
            for grant_id in reversed(grant_ids):
                try:
                    cleanup_failed |= (
                        post(
                            owner, f"{API}/qms-access/grants/{grant_id}/revoke", {}
                        ).status_code
                        != 200
                    )
                except Exception:  # noqa: BLE001 -- attempt all cleanup without exposing credentials
                    cleanup_failed = True
            for client in clients:
                if "pm_csrf" in client.cookies:
                    try:
                        cleanup_failed |= (
                            client.post(
                                f"{API}/auth/logout", headers=csrf(client)
                            ).status_code
                            != 204
                        )
                    except Exception:  # noqa: BLE001 -- close remaining local test sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError(
                    "risk E2E grants/session cleanup could not be verified"
                )
    print("OIDC, risk scoring, review authority, workflow, audit and web proxy: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- never expose local credentials, auth URLs or tokens
        raise SystemExit(
            f"Risk E2E failed during {phase} ({type(error).__name__}); credentials redacted."
        ) from None
