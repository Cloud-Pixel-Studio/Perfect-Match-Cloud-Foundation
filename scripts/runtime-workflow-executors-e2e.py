"""Opt-in synthetic workflow QA on the fixed local development runtime only."""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path
from typing import Any

import httpx
from dotenv import dotenv_values

identity = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API = "http://127.0.0.1:8000"
stage = "initialization"


def call(
    client: httpx.Client,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    expected: int = 200,
) -> Any:
    response = client.request(
        method,
        API + path,
        json=body,
        headers=identity["csrf"](client) if method != "GET" else {},
    )
    if response.status_code != expected:
        raise RuntimeError(f"{stage}: HTTP {response.status_code}")
    return response.json()


def graph(owner: httpx.Client, code: str, assignment: dict[str, Any] | None) -> Any:
    definition = call(
        owner,
        "POST",
        "/workflows",
        {
            "code": code,
            "name": "DEMO QA · Validación de ejecutores",
            "description": "Solo datos ficticios de prueba.",
        },
        expected=201,
    )
    version = call(
        owner, "POST", f"/workflows/{definition['id']}/versions", expected=201
    )
    base = f"/workflows/versions/{version['id']}"
    work = call(
        owner,
        "POST",
        base + "/steps",
        {
            "step_key": "work",
            "name": "Paso ficticio de QA",
            "step_type": "task" if assignment else "end",
            "is_start": True,
            "position": 0,
        },
        expected=201,
    )
    if assignment:
        end = call(
            owner,
            "POST",
            base + "/steps",
            {
                "step_key": "end",
                "name": "Fin de QA",
                "step_type": "end",
                "position": 1,
            },
            expected=201,
        )
        call(
            owner,
            "POST",
            base + "/transitions",
            {
                "from_step_id": work["id"],
                "to_step_id": end["id"],
                "transition_key": "finish",
                "label": "Completar QA ficticia",
            },
            expected=201,
        )
        call(
            owner,
            "POST",
            base + "/assignments",
            {"step_id": work["id"], **assignment},
            expected=201,
        )
    return {"definition": definition, "version": version, "base": base}


def main() -> None:
    global stage
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="create NEW synthetic QA records"
    )
    if not parser.parse_args().apply:
        print("No writes. Use --apply after a verified local database checkpoint.")
        return
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("requires local development environment")
    if not env.get("KEYCLOAK_OWNER_PASSWORD") or not env.get(
        "KEYCLOAK_USER_A_PASSWORD"
    ):
        raise RuntimeError("local QA credentials unavailable")
    checks = []
    with ExitStack() as stack:
        owner, operator = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(2)
        )
        try:
            stage = "authorized local login"
            for client, username, key in (
                (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
                (operator, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
            ):
                identity["login"](client, username, str(env[key]))
                identity["select_tenant"](client)
            person = call(operator, "GET", "/auth/me")["id"]
            units = call(owner, "GET", "/organization/units?limit=100")
            if len(units) >= 100:
                raise RuntimeError("unit catalog full; no absence inferred")
            practice = next(row for row in units if row["code"] == "DEMO-PRACTICA")
            suffix = datetime.now(UTC).strftime("%m%d%H%M%S")
            stage = "empty unit cannot execute"
            unit = call(
                owner,
                "POST",
                "/organization/units",
                {
                    "code": "LAB-WFX-" + suffix,
                    "name": "DEMO QA · Equipo vacío",
                    "unit_type": "team",
                    "parent_id": practice["id"],
                },
                expected=201,
            )
            empty = graph(
                owner,
                "LAB-WFX-E-" + suffix,
                {
                    "target_type": "organization_unit",
                    "target_organization_unit_id": unit["id"],
                },
            )
            call(owner, "POST", empty["base"] + "/publish", expected=409)
            assert call(owner, "GET", empty["base"])["status"] == "draft"
            checks.extend(
                ("empty unit publication denied", "failed publication preserves draft")
            )
            call(
                owner,
                "PATCH",
                f"/workflows/{empty['definition']['id']}",
                {"status": "retired"},
            )
            call(owner, "POST", f"/organization/units/{unit['id']}/archive")

            stage = "terminal start rejected"
            terminal = graph(owner, "LAB-WFX-T-" + suffix, None)
            call(owner, "POST", terminal["base"] + "/publish", expected=409)
            checks.append("terminal start publication denied")
            call(
                owner,
                "PATCH",
                f"/workflows/{terminal['definition']['id']}",
                {"status": "retired"},
            )

            stage = "eligible user executes real task"
            valid = graph(
                owner,
                "LAB-WFX-U-" + suffix,
                {
                    "target_type": "user",
                    "target_user_id": person,
                },
            )
            call(owner, "POST", valid["base"] + "/publish")
            instance = call(
                owner,
                "POST",
                "/workflow-instances",
                {
                    "workflow_version_id": valid["version"]["id"],
                    "title": "DEMO QA · Ejecutar paso ficticio",
                },
                expected=201,
            )
            actions = call(
                operator, "GET", f"/workflow-instances/{instance['id']}/actions"
            )
            completed = call(
                operator,
                "POST",
                f"/workflow-instances/{instance['id']}/transition",
                {
                    "expected_version": instance["row_version"],
                    "transition_id": actions[0]["id"],
                },
            )
            assert completed["status"] == "completed"
            history = call(
                owner, "GET", f"/workflow-instances/{instance['id']}/history"
            )
            assert {event["event_type"] for event in history} >= {
                "started",
                "transitioned",
                "completed",
            }
            checks.extend(
                (
                    "valid publication and start",
                    "assigned operator completes step",
                    "history retained",
                )
            )

            stage = "retired definition cannot start new work"
            call(
                owner,
                "PATCH",
                f"/workflows/{valid['definition']['id']}",
                {"status": "retired"},
            )
            call(
                owner,
                "POST",
                "/workflow-instances",
                {
                    "workflow_version_id": valid["version"]["id"],
                    "title": "Must not start",
                },
                expected=409,
            )
            assert (
                call(owner, "GET", f"/workflow-instances/{instance['id']}/history")
                == history
            )
            checks.extend(
                (
                    "retired definition start denied",
                    "existing history unchanged after denied start",
                )
            )
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "checks": checks,
                        "synthetic_qa_only": True,
                        "grant_or_role_changes": 0,
                        "deletions": 0,
                        "run_suffix": suffix,
                    }
                )
            )
        finally:
            for client in (owner, operator):
                if "pm_csrf" in client.cookies:
                    try:
                        client.post(
                            API + "/auth/logout", headers=identity["csrf"](client)
                        )
                    except httpx.HTTPError:
                        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- do not print auth response data/URLs
        message = str(error) if type(error) is RuntimeError else type(error).__name__
        raise SystemExit("Workflow local QA stopped: " + message) from None
