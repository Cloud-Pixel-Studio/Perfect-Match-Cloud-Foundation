"""Exercise scoped NCR lifecycle through local OIDC, API, audit and web proxy."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from sys import argv
from uuid import uuid4

import httpx
from dotenv import dotenv_values

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
        raise RuntimeError("NCR E2E requires local development environment")
    grants: list[str] = []
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
            active = {
                (r["user_id"], r["unit_id"], r["capability"])
                for r in owner.get(f"{API}/qms-access/grants").json()
                if r["status"] == "active"
            }
            phase = "temporary NCR responsibilities"
            for prefix, capabilities in (
                ("pmc-user-a", ("processes.read", "ncr.read", "ncr.manage")),
                ("pmc-multi-user", ("ncr.read", "ncr.review")),
            ):
                for capability in capabilities:
                    if (users[prefix], unit["id"], capability) in active:
                        continue
                    granted = post(
                        owner,
                        f"{API}/qms-access/grants",
                        {
                            "user_id": users[prefix],
                            "unit_id": unit["id"],
                            "capability": capability,
                        },
                    )
                    if granted.status_code != 201:
                        raise AssertionError("temporary NCR responsibility rejected")
                    grants.append(granted.json()["id"])
            processes = author.get(
                f"{API}/processes", params={"unit_id": unit["id"], "limit": 50}
            ).json()
            process = next(r for r in processes if r["status"] == "active")
            suffix = uuid4().hex[:10].upper()
            today = datetime.now(UTC).date()
            code = f"DEV-E2E-NCR-{suffix}"
            phase = "NCR creation and server-derived detector"
            created = post(
                author,
                f"{API}/nonconformities",
                {
                    "unit_id": unit["id"],
                    "process_id": process["id"],
                    "code": code,
                    "name": "Superseded instruction at fictional workstation",
                    "source_type": "document",
                    "severity": "major",
                    "description": "Fictional superseded instruction found during local validation.",
                    "detected_date": today.isoformat(),
                    "target_date": (today - timedelta(days=1)).isoformat(),
                    "owner_user_id": users["pmc-user-a"],
                    "containment_required": True,
                    "containment_action": "Remove the fictional superseded copy.",
                    "containment_owner_user_id": users["pmc-user-a"],
                },
            )
            if created.status_code != 201:
                raise AssertionError("NCR creation failed")
            ncr = created.json()
            if (
                ncr["detected_by_user_id"] != users["pmc-user-a"]
                or not ncr["is_overdue"]
            ):
                raise AssertionError("NCR detection or overdue calculation incorrect")

            def transition(
                client: httpx.Client, target: str, **extra: object
            ) -> httpx.Response:
                return post(
                    client,
                    f"{API}/nonconformities/{ncr['id']}/transition",
                    {
                        "expected_version": ncr["row_version"],
                        "target_state": target,
                        "decision": "Fictional local workflow validation.",
                        **extra,
                    },
                )

            phase = "author opening and restricted review"
            opened = transition(author, "open")
            if opened.status_code != 200:
                raise AssertionError("NCR author could not open draft")
            ncr = opened.json()
            if transition(author, "investigation").status_code != 403:
                raise AssertionError("NCR author received implicit review authority")
            if (
                owner.get(
                    f"{API}/nonconformities", params={"unit_id": unit["id"]}
                ).status_code
                != 403
            ):
                raise AssertionError("tenant owner received implicit NCR access")
            if transition(reviewer, "investigation").status_code not in {409, 422}:
                raise AssertionError(
                    "NCR investigation bypassed incomplete required containment"
                )
            started = transition(reviewer, "containment")
            if started.status_code != 200:
                raise AssertionError("NCR containment transition failed")
            ncr = started.json()
            bypass = author.patch(
                f"{API}/nonconformities/{ncr['id']}",
                json={
                    "expected_version": ncr["row_version"],
                    "containment_required": False,
                },
                headers=csrf(author),
            )
            if bypass.status_code not in {409, 422}:
                raise AssertionError(
                    "NCR required containment could be disabled after opening"
                )
            phase = "containment completion and investigation"
            completed = author.patch(
                f"{API}/nonconformities/{ncr['id']}",
                json={
                    "expected_version": ncr["row_version"],
                    "containment_completed": True,
                    "containment_date": today.isoformat(),
                },
                headers=csrf(author),
            )
            if completed.status_code != 200:
                raise AssertionError("NCR containment completion failed")
            ncr = completed.json()
            investigated = transition(reviewer, "investigation")
            if investigated.status_code != 200:
                raise AssertionError(
                    "NCR investigation remained blocked after containment"
                )
            ncr = investigated.json()
            edited = author.patch(
                f"{API}/nonconformities/{ncr['id']}",
                json={
                    "expected_version": ncr["row_version"],
                    "root_cause_summary": "Fictional distribution handoff had no second check.",
                    "disposition": "rework",
                    "disposition_notes": "Reissue the current fictional instruction.",
                },
                headers=csrf(author),
            )
            if edited.status_code != 200:
                raise AssertionError("NCR investigation details could not be saved")
            ncr = edited.json()
            phase = "version conflict and same-origin proxy"
            stale = author.patch(
                f"{API}/nonconformities/{ncr['id']}",
                json={"expected_version": 1, "name": "Stale overwrite"},
                headers=csrf(author),
            )
            if stale.status_code != 409:
                raise AssertionError("NCR stale update was accepted")
            proxy = author.get(
                f"{WEB}/api/identity/nonconformities",
                params={"unit_id": unit["id"], "q": code},
            )
            if proxy.status_code != 200 or not any(
                r["id"] == ncr["id"] for r in proxy.json()
            ):
                raise AssertionError("NCR proxy did not return scoped record")
            phase = "verification and controlled closure"
            for state in ("action_required", "verification"):
                moved = transition(reviewer, state)
                if moved.status_code != 200:
                    raise AssertionError("NCR controlled transition failed")
                ncr = moved.json()
            if transition(reviewer, "closed").status_code not in {409, 422}:
                raise AssertionError("NCR closure did not require notes")
            closed = transition(
                reviewer,
                "closed",
                closure_notes="Fictional verification completed with controlled disposition.",
            )
            if (
                closed.status_code != 200
                or closed.json()["state"] != "closed"
                or closed.json()["is_overdue"]
            ):
                raise AssertionError("NCR closure metadata or overdue state failed")
            ncr = closed.json()
            immutable = author.patch(
                f"{API}/nonconformities/{ncr['id']}",
                json={
                    "expected_version": ncr["row_version"],
                    "name": "Attempt terminal rewrite",
                },
                headers=csrf(author),
            )
            if immutable.status_code != 409:
                raise AssertionError("closed NCR could be rewritten")
            phase = "audit evidence"
            events = owner.get(f"{API}/audit/events?limit=100").json()["items"]
            actions = {r["action"] for r in events if r["resource_id"] == ncr["id"]}
            if not {"ncr.created", "ncr.updated", "ncr.transitioned"} <= actions:
                raise AssertionError("NCR audit events were incomplete")
            if "--visual-hold" in argv:
                phase = "temporary visual review of synthetic closed NCR"
                print(f"Synthetic NCR for visual review: {code}", flush=True)
                input("Press Enter to revoke the temporary grants and close test sessions: ")
        finally:
            for grant_id in reversed(grants):
                try:
                    cleanup_failed |= (
                        post(
                            owner, f"{API}/qms-access/grants/{grant_id}/revoke", {}
                        ).status_code
                        != 200
                    )
                except Exception:  # noqa: BLE001 -- finish cleanup without exposing credentials
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
                    except Exception:  # noqa: BLE001 -- finish closing local test sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError(
                    "NCR E2E grant/session cleanup could not be verified"
                )
    print(
        "OIDC, NCR containment gates, review authority, lifecycle, audit and web proxy: PASS"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- avoid logging credentials, tokens or auth URLs
        raise SystemExit(
            f"NCR E2E failed during {phase} ({type(error).__name__}); credentials redacted."
        ) from None
