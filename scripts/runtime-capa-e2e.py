"""Exercise CAPA intake through local OIDC, API, proxy and audit."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
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
        raise RuntimeError("CAPA E2E requires local development environment")
    grants: list[str] = []
    cleanup_failed = False
    with ExitStack() as stack:
        owner, author, reviewer = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(3)
        )
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
            author_id = next(r["id"] for r in members if r["display_name"].startswith("pmc-user-a"))
            reviewer_id = next(r["id"] for r in members if r["display_name"].startswith("pmc-multi-user"))
            unit = next(
                r for r in owner.get(f"{API}/organization/units?limit=100").json()
                if r["code"] == "DEV-ACCESS-UI" and r["status"] == "active"
            )
            active = {
                (r["user_id"], r["unit_id"], r["capability"])
                for r in owner.get(f"{API}/qms-access/grants").json()
                if r["status"] == "active"
            }
            phase = "temporary CAPA and origin responsibilities"
            for capability in ("processes.read", "ncr.read", "ncr.manage", "capa.read", "capa.manage"):
                if (author_id, unit["id"], capability) in active:
                    continue
                granted = post(owner, f"{API}/qms-access/grants", {
                    "user_id": author_id, "unit_id": unit["id"], "capability": capability,
                })
                if granted.status_code != 201:
                    raise AssertionError("temporary CAPA responsibility rejected")
                grants.append(granted.json()["id"])
            for capability in ("ncr.read", "capa.read", "capa.review"):
                if (reviewer_id, unit["id"], capability) in active:
                    continue
                granted = post(owner, f"{API}/qms-access/grants", {
                    "user_id": reviewer_id, "unit_id": unit["id"], "capability": capability,
                })
                if granted.status_code != 201:
                    raise AssertionError("temporary CAPA reviewer responsibility rejected")
                grants.append(granted.json()["id"])
            process = next(
                r for r in author.get(f"{API}/processes", params={
                    "unit_id": unit["id"], "limit": 50,
                }).json() if r["status"] == "active"
            )
            suffix = uuid4().hex[:10].upper()
            phase = "scoped NCR origin and CAPA creation"
            origin = post(author, f"{API}/nonconformities", {
                "unit_id": unit["id"], "process_id": process["id"],
                "code": f"DEV-E2E-NCR-CAPA-{suffix}", "name": "Fictional source issue",
                "description": "Synthetic source for local CAPA validation.",
                "detected_date": datetime.now(UTC).date().isoformat(),
                "owner_user_id": author_id,
            })
            if origin.status_code != 201:
                raise AssertionError("CAPA source creation failed")
            ncr = origin.json()
            created = post(author, f"{API}/capas", {
                "unit_id": unit["id"], "process_id": process["id"],
                "code": f"DEV-E2E-CAPA-{suffix}", "name": "Fictional receiving correction",
                "source_type": "ncr", "source_ncr_id": ncr["id"],
                "problem_statement": "Synthetic receiving condition for local CAPA validation.",
                "owner_user_id": author_id, "root_cause_method": "5why",
            })
            if created.status_code != 201:
                raise AssertionError("CAPA creation failed")
            row = created.json()
            if row["state"] != "draft" or row["source_code"] != ncr["code"]:
                raise AssertionError("CAPA provenance snapshot or draft state incorrect")
            phase = "access, version and web proxy"
            if owner.get(f"{API}/capas", params={"unit_id": unit["id"]}).status_code != 403:
                raise AssertionError("tenant owner received implicit CAPA authority")
            changed = author.patch(f"{API}/capas/{row['id']}", json={
                "expected_version": 1, "name": "Fictional receiving correction reviewed",
            }, headers=csrf(author))
            if changed.status_code != 200 or changed.json()["row_version"] != 2:
                raise AssertionError("CAPA draft edit failed")
            stale = author.patch(f"{API}/capas/{row['id']}", json={
                "expected_version": 1, "name": "Stale overwrite",
            }, headers=csrf(author))
            if stale.status_code != 409:
                raise AssertionError("CAPA stale edit was accepted")
            proxy = author.get(f"{WEB}/api/identity/capas", params={
                "unit_id": unit["id"], "q": row["code"],
            })
            if proxy.status_code != 200 or not any(r["id"] == row["id"] for r in proxy.json()):
                raise AssertionError("CAPA web proxy did not return scoped draft")
            phase = "guided root cause analysis"
            started = post(author, f"{API}/capas/{row['id']}/analysis/start", {
                "expected_version": 2,
            })
            if started.status_code != 200 or started.json()["state"] != "analysis":
                raise AssertionError("CAPA analysis did not start")
            row = started.json()
            if sorted(row["analysis_data"]) != ["why1", "why2", "why3", "why4", "why5"]:
                raise AssertionError("5 Why scaffold was not fixed")
            if author.patch(f"{API}/capas/{row['id']}", json={
                "expected_version": row["row_version"], "root_cause_method": "fishbone",
            }, headers=csrf(author)).status_code != 409:
                raise AssertionError("CAPA method changed after analysis started")
            answers = {**row["analysis_data"], "why1": "Fictional handoff lacked an owner."}
            analyzed = author.patch(f"{API}/capas/{row['id']}/analysis", json={
                "expected_version": row["row_version"], "analysis_data": answers,
                "analysis_summary": "Synthetic receiving investigation.",
                "verified_root_cause": "Fictional ownership gap.",
            }, headers=csrf(author))
            if analyzed.status_code != 200 or analyzed.json()["row_version"] != 4:
                raise AssertionError("CAPA analysis could not be saved")
            row = analyzed.json()
            if author.patch(f"{API}/capas/{row['id']}/analysis", json={
                "expected_version": 3, "analysis_data": answers,
            }, headers=csrf(author)).status_code != 409:
                raise AssertionError("stale CAPA analysis overwrite was accepted")
            phase = "verified investigation to action plan"
            planned = post(author, f"{WEB}/api/identity/capas/{row['id']}/plan/start", {
                "expected_version": row["row_version"],
                "plan_summary": "Assign a responsible person and correct the synthetic control.",
            })
            if planned.status_code != 200 or planned.json()["state"] != "action_planned":
                raise AssertionError("CAPA action plan did not start through the web proxy")
            row = planned.json()
            if row["planned_by_user_id"] != author_id or row["row_version"] != 5:
                raise AssertionError("CAPA planning actor or version incorrect")
            if author.patch(f"{API}/capas/{row['id']}/analysis", json={
                "expected_version": row["row_version"], "analysis_data": answers,
            }, headers=csrf(author)).status_code != 409:
                raise AssertionError("verified CAPA investigation was editable after planning")
            phase = "assigned CAPA action register"
            assigned = post(author, f"{WEB}/api/identity/capas/{row['id']}/actions", {
                "expected_capa_version": row["row_version"],
                "title": "Assign fictional receiving control owner",
                "description": "Document and communicate the fictional control responsibility.",
                "owner_user_id": author_id,
                "due_date": (datetime.now(UTC) + timedelta(days=7)).date().isoformat(),
            })
            if assigned.status_code != 201 or assigned.json()["state"] != "open":
                raise AssertionError("CAPA action could not be assigned through the web proxy")
            action = assigned.json()
            listed = author.get(f"{WEB}/api/identity/capas/{row['id']}/actions")
            if listed.status_code != 200 or not any(item["id"] == action["id"] for item in listed.json()):
                raise AssertionError("CAPA action register did not return assigned action")
            revised = author.patch(f"{API}/capas/{row['id']}/actions/{action['id']}", json={
                "expected_capa_version": 6, "expected_action_version": 1,
                "description": "Revised fictional control responsibility.",
            }, headers=csrf(author))
            if revised.status_code != 200 or revised.json()["row_version"] != 2:
                raise AssertionError("CAPA action versioned edit failed")
            if author.patch(f"{API}/capas/{row['id']}/actions/{action['id']}", json={
                "expected_capa_version": 6, "expected_action_version": 1,
                "title": "Stale edit",
            }, headers=csrf(author)).status_code != 409:
                raise AssertionError("stale CAPA action edit was accepted")
            phase = "CAPA execution and independent action verification"
            implementation = post(author, f"{API}/capas/{row['id']}/implementation/start", {
                "expected_version": 7,
            })
            if implementation.status_code != 200 or implementation.json()["state"] != "implementation":
                raise AssertionError("CAPA implementation did not start")
            if author.patch(f"{API}/capas/{row['id']}/actions/{action['id']}", json={
                "expected_capa_version": 8, "expected_action_version": 2,
                "title": "Late plan rewrite",
            }, headers=csrf(author)).status_code != 409:
                raise AssertionError("CAPA action plan was editable during implementation")
            started_action = post(author, f"{API}/capas/{row['id']}/actions/{action['id']}/transition", {
                "expected_capa_version": 8, "expected_action_version": 2,
                "target_state": "in_progress",
            })
            if started_action.status_code != 200 or started_action.json()["state"] != "in_progress":
                raise AssertionError("CAPA action did not start")
            completed_action = post(author, f"{API}/capas/{row['id']}/actions/{action['id']}/transition", {
                "expected_capa_version": 9, "expected_action_version": 3,
                "target_state": "completed",
            })
            if completed_action.status_code != 200 or completed_action.json()["completed_by_user_id"] != author_id:
                raise AssertionError("CAPA action completion actor is incorrect")
            verified_action = post(reviewer, f"{WEB}/api/identity/capas/{row['id']}/actions/{action['id']}/transition", {
                "expected_capa_version": 10, "expected_action_version": 4,
                "target_state": "verified", "verification_notes": "Independent synthetic review.",
            })
            if verified_action.status_code != 200 or verified_action.json()["verified_by_user_id"] != reviewer_id:
                raise AssertionError("independent CAPA action verification failed")
            phase = "CAPA effectiveness review gate"
            review_started = post(author, f"{WEB}/api/identity/capas/{row['id']}/effectiveness-review/start", {
                "expected_version": 11,
            })
            if review_started.status_code != 200 or review_started.json()["state"] != "effectiveness_review":
                raise AssertionError("CAPA effectiveness review did not start")
            phase = "independent effectiveness decision and closure"
            effectiveness = post(reviewer, f"{WEB}/api/identity/capas/{row['id']}/effectiveness-reviews", {
                "expected_version": 12, "decision": "effective",
                "notes": "Synthetic follow-up confirms no recurrence.",
            })
            if effectiveness.status_code != 201 or effectiveness.json()["cycle_number"] != 1:
                raise AssertionError("CAPA effectiveness decision did not record")
            closed = post(reviewer, f"{API}/capas/{row['id']}/close", {
                "expected_version": 13,
                "closure_notes": "Synthetic CAPA closed after independent effectiveness review.",
            })
            if closed.status_code != 200 or closed.json()["state"] != "closed":
                raise AssertionError("effective CAPA did not close")
            phase = "multiple Fishbone causes with confirmed evidence"
            fishbone = post(author, f"{API}/capas", {
                "unit_id": unit["id"], "process_id": process["id"],
                "code": f"DEV-E2E-FISHBONE-{suffix}", "name": "Fictional cause comparison",
                "source_type": "other", "problem_statement": "Synthetic test of multiple causes.",
                "source_reference": f"External synthetic case {suffix}",
                "root_cause_method": "fishbone",
            })
            if fishbone.status_code != 201:
                raise AssertionError("Fishbone CAPA creation failed")
            if fishbone.json()["source_reference"] != f"External synthetic case {suffix}":
                raise AssertionError("CAPA external source reference was not preserved")
            fishbone_row = fishbone.json()
            started_fishbone = post(author, f"{API}/capas/{fishbone_row['id']}/analysis/start", {
                "expected_version": fishbone_row["row_version"],
            })
            if started_fishbone.status_code != 200:
                raise AssertionError("Fishbone analysis did not start")
            fishbone_row = started_fishbone.json()
            fishbone_data = dict(fishbone_row["analysis_data"])
            if fishbone_data["people"] != []:
                raise AssertionError("Fishbone scaffold is not an empty cause list")
            fishbone_data["people"] = [
                {"statement": "Fictional role handoff gap", "evidence": "Fictional log 1",
                 "rationale": "Repeated in the synthetic sample", "confirmed": True},
                {"statement": "Fictional training concern", "evidence": "",
                 "rationale": "", "confirmed": False},
            ]
            invalid_fishbone = dict(fishbone_data)
            invalid_fishbone["people"] = [{**fishbone_data["people"][0], "evidence": ""}]
            if author.patch(f"{API}/capas/{fishbone_row['id']}/analysis", json={
                "expected_version": fishbone_row["row_version"],
                "analysis_data": invalid_fishbone,
            }, headers=csrf(author)).status_code != 422:
                raise AssertionError("confirmed Fishbone cause without evidence was accepted")
            saved_fishbone = author.patch(f"{WEB}/api/identity/capas/{fishbone_row['id']}/analysis", json={
                "expected_version": fishbone_row["row_version"],
                "analysis_data": fishbone_data,
            }, headers=csrf(author))
            if saved_fishbone.status_code != 200 or len(saved_fishbone.json()["analysis_data"]["people"]) != 2:
                raise AssertionError("multiple Fishbone causes were not saved through the web proxy")
            phase = "reviewer-authorized CAPA cancellation"
            cancelled_fishbone = post(reviewer, f"{API}/capas/{fishbone_row['id']}/cancel", {
                "expected_version": saved_fishbone.json()["row_version"],
                "reason": "Synthetic analysis cancelled after duplicate investigation.",
            })
            if cancelled_fishbone.status_code != 200 or cancelled_fishbone.json()["state"] != "cancelled":
                raise AssertionError("CAPA cancellation did not preserve reviewer decision")
            phase = "audit and target-read revocation"
            events = owner.get(f"{API}/audit/events?limit=100").json()["items"]
            actions = {r["action"] for r in events if r["resource_id"] == row["id"]}
            if not {"capa.created", "capa.updated", "capa.analysis_started", "capa.analysis_updated", "capa.plan_started", "capa.implementation_started", "capa.effectiveness_review_started", "capa.effectiveness_decided", "capa.closed"} <= actions:
                raise AssertionError("CAPA audit history incomplete")
            action_events = {r["action"] for r in events if r["resource_id"] == action["id"]}
            if action_events != {"capa.action_created", "capa.action_updated", "capa.action_transitioned"}:
                raise AssertionError("CAPA action audit history incomplete")
            review_events = {r["action"] for r in events if r["resource_id"] == effectiveness.json()["id"]}
            if review_events != {"capa.effectiveness_recorded"}:
                raise AssertionError("CAPA effectiveness audit history incomplete")
            fishbone_events = {r["action"] for r in events if r["resource_id"] == fishbone_row["id"]}
            if "capa.cancelled" not in fishbone_events:
                raise AssertionError("CAPA cancellation audit history incomplete")
            source_grant = next((r for r in owner.get(f"{API}/qms-access/grants").json()
                                 if r["user_id"] == author_id and r["unit_id"] == unit["id"]
                                 and r["capability"] == "ncr.read" and r["status"] == "active"), None)
            if source_grant is None:
                raise AssertionError("source read grant not found")
            if source_grant["id"] in grants:
                revoked = post(owner, f"{API}/qms-access/grants/{source_grant['id']}/revoke", {})
                if revoked.status_code != 200:
                    raise AssertionError("source read grant could not be revoked")
                grants = [item for item in grants if item != source_grant["id"]]
                if author.get(f"{API}/capas/{row['id']}").status_code != 404:
                    raise AssertionError("CAPA remained visible after source read revocation")
                if author.get(f"{API}/capas/{row['id']}/actions").status_code != 404:
                    raise AssertionError("CAPA actions remained visible after source read revocation")
        finally:
            for grant_id in reversed(grants):
                try:
                    cleanup_failed |= post(owner, f"{API}/qms-access/grants/{grant_id}/revoke", {}).status_code != 200
                except Exception:  # noqa: BLE001 -- finish cleanup without exposing credentials
                    cleanup_failed = True
            for client in (owner, author, reviewer):
                if "pm_csrf" in client.cookies:
                    try:
                        cleanup_failed |= client.post(f"{API}/auth/logout", headers=csrf(client)).status_code != 204
                    except Exception:  # noqa: BLE001 -- close local test sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError("CAPA E2E grant/session cleanup could not be verified")
    print("OIDC, CAPA analysis, execution, independent review, closure, cancellation and audit: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- redact credentials, tokens and auth URLs
        raise SystemExit(
            f"CAPA E2E failed during {phase} ({type(error).__name__}); credentials redacted."
        ) from None
