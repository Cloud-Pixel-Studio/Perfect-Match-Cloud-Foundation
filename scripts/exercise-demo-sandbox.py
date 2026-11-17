"""Opt-in API round trips using NEW synthetic records in DEMO-PRACTICA only.

Run with --apply after a verified DB backup. Retains history, never deletes.
This exercises API commands, not every browser button or complete Odoo parity.
"""

import argparse
import json
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path

import httpx
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    if not parser.parse_args().apply:
        print("No writes. --apply explicitly creates synthetic QA records.")
        return
    D = run_path(str(Path(__file__).with_name("seed-demo-sandbox.py")))
    identity = D["IDENTITY"]
    API = D["API"]
    Sandbox = D["Sandbox"]
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    D["validate_environment"](env)
    if not env.get("KEYCLOAK_USER_B_PASSWORD"):
        raise SystemExit("Independent development-company test account unavailable")
    checks = []
    stage = "login"
    with ExitStack() as stack:
        clients = [
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(4)
        ]
        owner, author, reviewer, foreign = clients
        try:
            for c, u, k in [
                (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
                (author, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
                (reviewer, "pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
            ]:
                identity["login"](c, u, str(env[k]))
                identity["select_tenant"](c)
            s = Sandbox(owner, author, reviewer)
            r = s.request

            def req(c, m, p, b=None, **kw):
                s.stage = stage
                return r(c, m, p, b, **kw)

            def ok(name, condition=True):
                if not condition:
                    raise RuntimeError(name)
                checks.append(name)

            unit = next(
                x
                for x in s.rows(owner, "/organization/units", paginated=False)
                if x["code"] == D["UNIT_CODE"]
            )
            process = next(
                x
                for x in s.rows(author, "/processes", unit_id=unit["id"])
                if x["code"] == "LAB-PROC-001"
            )
            scope = {"unit_id": unit["id"], "process_id": process["id"]}
            aid = req(author, "GET", "/auth/me")["id"]
            rid = req(reviewer, "GET", "/auth/me")["id"]
            suffix = datetime.now(UTC).strftime("%m%d%H%M%S")
            today = datetime.now(UTC).date()
            deadline = (today + timedelta(days=10)).isoformat()
            marker = "QA sintética de práctica. Sin cliente real."
            stage = "organization"
            child = req(
                owner,
                "POST",
                "/organization/units",
                {
                    "code": "LAB-QA-" + suffix,
                    "name": "DEMO QA temporal",
                    "unit_type": "team",
                    "parent_id": unit["id"],
                    "description": marker,
                },
            )
            child = req(
                owner,
                "PATCH",
                f"/organization/units/{child['id']}",
                {"name": "DEMO QA modificada"},
            )
            ok("organization create/edit", child["name"] == "DEMO QA modificada")
            stage = "responsibilities"
            g = req(
                owner,
                "POST",
                "/qms-access/grants",
                {
                    "user_id": rid,
                    "unit_id": child["id"],
                    "capability": "processes.read",
                },
            )
            effective = req(
                reviewer,
                "GET",
                "/qms-access/effective",
                params={"unit_id": child["id"]},
            )["capabilities"]
            ok("grant effective", "processes.read" in effective)
            req(owner, "POST", f"/qms-access/grants/{g['id']}/revoke", {})
            ok(
                "grant revoked",
                "processes.read"
                not in req(
                    reviewer,
                    "GET",
                    "/qms-access/effective",
                    params={"unit_id": child["id"]},
                )["capabilities"],
            )
            child = req(owner, "POST", f"/organization/units/{child['id']}/archive", {})
            ok("organization archive", child["status"] == "archived")
            child = req(owner, "POST", f"/organization/units/{child['id']}/restore", {})
            ok("organization restore", child["status"] == "active")
            req(owner, "POST", f"/organization/units/{child['id']}/archive", {})
            stage = "process"
            p = req(
                author,
                "POST",
                "/processes",
                {
                    "unit_id": unit["id"],
                    "code": "LAB-QA-P-" + suffix,
                    "name": "DEMO QA proceso",
                    "process_type": "support",
                    "description": marker,
                },
            )
            p = req(
                author,
                "PATCH",
                f"/processes/{p['id']}",
                {
                    "expected_version": p["row_version"],
                    "name": "DEMO QA proceso editado",
                    "site_ids": [],
                },
            )
            ok("process create/edit", p["name"].endswith("editado"))
            p = req(
                author,
                "POST",
                f"/processes/{p['id']}/archive",
                {"expected_version": p["row_version"]},
            )
            ok("process archive", p["status"] == "archived")
            p = req(
                author,
                "POST",
                f"/processes/{p['id']}/restore",
                {"expected_version": p["row_version"]},
            )
            ok("process restore", p["status"] == "active")
            req(
                author,
                "POST",
                f"/processes/{p['id']}/archive",
                {"expected_version": p["row_version"]},
            )
            stage = "risk"
            risk = req(
                author,
                "POST",
                "/risks",
                {
                    **scope,
                    "code": "LAB-QA-R-" + suffix,
                    "name": "DEMO QA riesgo",
                    "description": marker,
                },
            )
            risk = req(
                author,
                "PATCH",
                f"/risks/{risk['id']}",
                {
                    "expected_version": risk["row_version"],
                    "name": "DEMO QA riesgo editado",
                },
            )
            ok("risk create/edit", risk["name"].endswith("editado"))
            for target in ("assessed", "monitoring", "closed"):
                risk = req(
                    author,
                    "POST",
                    f"/risks/{risk['id']}/transition",
                    {
                        "expected_version": risk["row_version"],
                        "target_state": target,
                        "decision": marker,
                        **({"closure_notes": marker} if target == "closed" else {}),
                    },
                )
            ok("risk controlled close", risk["state"] == "closed")
            response = author.patch(
                API + f"/risks/{risk['id']}",
                json={"expected_version": risk["row_version"], "name": "not allowed"},
                headers=identity["csrf"](author),
            )
            ok("closed risk immutable", response.status_code == 409)
            stage = "nonconformity"
            n = req(
                author,
                "POST",
                "/nonconformities",
                {
                    **scope,
                    "code": "LAB-QA-N-" + suffix,
                    "name": "DEMO QA NCR",
                    "description": marker,
                },
            )
            n = req(
                author,
                "PATCH",
                f"/nonconformities/{n['id']}",
                {
                    "expected_version": n["row_version"],
                    "description": marker + " Edición.",
                },
            )
            ok("NCR create/edit", n["description"].endswith("Edición."))
            n = req(
                author,
                "POST",
                f"/nonconformities/{n['id']}/transition",
                {
                    "expected_version": n["row_version"],
                    "target_state": "cancelled",
                    "decision": marker,
                },
            )
            ok("NCR cancel", n["state"] == "cancelled")
            stage = "CAPA"
            c = req(
                author,
                "POST",
                "/capas",
                {
                    **scope,
                    "code": "LAB-QA-C-" + suffix,
                    "name": "DEMO QA CAPA",
                    "source_type": "other",
                    "problem_statement": marker,
                },
            )
            c = req(
                author,
                "PATCH",
                f"/capas/{c['id']}",
                {"expected_version": c["row_version"], "name": "DEMO QA CAPA editada"},
            )
            ok("CAPA create/edit", c["name"].endswith("editada"))
            c = req(
                reviewer,
                "POST",
                f"/capas/{c['id']}/cancel",
                {"expected_version": c["row_version"], "reason": marker},
            )
            ok("CAPA cancel", c["state"] == "cancelled")
            stage = "documents"
            doc = req(
                author,
                "POST",
                "/documents",
                {
                    **scope,
                    "code": "LAB-QA-D-" + suffix,
                    "title": "DEMO QA documento",
                    "document_type": "procedure",
                    "owner_user_id": aid,
                },
            )
            rev = req(
                author,
                "POST",
                f"/documents/{doc['id']}/revisions",
                {
                    "revision": "QA-1",
                    "change_summary": marker,
                    "revision_date": today.isoformat(),
                },
            )
            for index, label in enumerate(
                ["Initial practice file", "Revised practice file"], 1
            ):
                if index == 2:
                    denied = author.put(
                        API + f"/documents/{doc['id']}/revisions/{rev['id']}/file",
                        content=D["pdf_document"](label),
                        headers={
                            **identity["csrf"](author),
                            "Content-Type": "application/pdf",
                        },
                    )
                    ok("existing file overwrite denied", denied.status_code == 409)
                    rev = req(
                        author,
                        "POST",
                        f"/documents/{doc['id']}/revisions",
                        {
                            "revision": "QA-2",
                            "change_summary": marker + " Edición controlada.",
                            "revision_date": today.isoformat(),
                        },
                    )
                upload = author.put(
                    API + f"/documents/{doc['id']}/revisions/{rev['id']}/file",
                    content=D["pdf_document"](label),
                    headers={
                        **identity["csrf"](author),
                        "Content-Type": "application/pdf",
                    },
                )
                ok("document " + label, upload.status_code == 202)
            rev = req(author, "GET", f"/documents/{doc['id']}/revisions")[0]
            ok("document scanned clean", rev["file_state"] == "clean")
            doc = next(
                x
                for x in s.rows(author, "/documents", unit_id=unit["id"])
                if x["id"] == doc["id"]
            )
            doc = req(
                author,
                "POST",
                f"/documents/{doc['id']}/obsolete",
                {"expected_version": doc["row_version"]},
            )
            ok("document obsolete", doc["status"] == "obsolete")
            stage = "controls"
            control = req(
                author,
                "POST",
                "/controls",
                {
                    **scope,
                    "code": "LAB-QA-T-" + suffix,
                    "name": "DEMO QA control",
                    "objective": marker,
                },
            )
            control = req(
                author,
                "PATCH",
                f"/controls/{control['id']}",
                {
                    "expected_version": control["row_version"],
                    "objective": marker + " Editado.",
                },
            )
            ok("control create/edit", control["objective"].endswith("Editado."))
            activity = req(
                author,
                "POST",
                f"/controls/{control['id']}/activities",
                {"name": "DEMO QA actividad", "sequence": 10},
            )
            activity = req(
                author,
                "PATCH",
                f"/control-activities/{activity['id']}",
                {
                    "expected_version": activity["row_version"],
                    "name": "DEMO QA actividad editada",
                },
            )
            ok("activity definition edit", activity["name"].endswith("editada"))
            req(
                author,
                "POST",
                f"/controls/{control['id']}/evidence-requirements",
                {"name": "DEMO QA evidencia", "mandatory": True, "sequence": 10},
            )
            control = req(
                author,
                "POST",
                f"/controls/{control['id']}/activate",
                {"expected_version": control["row_version"]},
            )
            instance = req(
                author,
                "POST",
                "/control-instances",
                {
                    "control_id": control["id"],
                    "code": "LAB-QA-I-" + suffix,
                    "name": "DEMO QA implementación",
                    "owner_user_id": aid,
                },
                params=scope,
            )
            instance = req(
                author,
                "PATCH",
                f"/control-instances/{instance['id']}",
                {"expected_version": instance["row_version"], "notes": marker},
            )
            ok("implementation create/edit", instance["notes"] == marker)
            task = s.rows(
                author,
                "/control-instance-activities",
                paginated=False,
                instance_id=instance["id"],
            )[0]
            task = req(
                author,
                "PATCH",
                f"/control-instance-activities/{task['id']}",
                {
                    "expected_version": task["row_version"],
                    "assigned_to_user_id": aid,
                    "target_date": deadline,
                },
            )
            ok("task assigned", task["assigned_to_user_id"] == aid)
            task = req(
                author,
                "POST",
                f"/control-instance-activities/{task['id']}/transition",
                {
                    "expected_version": task["row_version"],
                    "target_status": "in_progress",
                    "decision": marker,
                },
            )
            ok("task in progress", task["status"] == "in_progress")
            ev = s.rows(
                author,
                "/control-instance-evidence",
                paginated=False,
                instance_id=instance["id"],
            )[0]
            ev = req(
                author,
                "PATCH",
                f"/control-instance-evidence/{ev['id']}",
                {"expected_version": ev["row_version"], "evidence_summary": marker},
            )
            ok("evidence edited", ev["evidence_summary"] == marker)
            ev = req(
                author,
                "POST",
                f"/control-instance-evidence/{ev['id']}/submit",
                {"expected_version": ev["row_version"]},
            )
            ok("evidence submitted", ev["status"] == "submitted")
            deny = author.post(
                API + f"/control-instance-evidence/{ev['id']}/review",
                json={
                    "expected_version": ev["row_version"],
                    "target_status": "accepted",
                    "decision": marker,
                },
                headers=identity["csrf"](author),
            )
            ok("unauthorized evidence review denied", deny.status_code == 403)
            ev = req(
                reviewer,
                "POST",
                f"/control-instance-evidence/{ev['id']}/review",
                {
                    "expected_version": ev["row_version"],
                    "target_status": "rejected",
                    "decision": "QA ficticia: corregir el registro antes de presentar.",
                },
            )
            ok("independent evidence rejection", ev["status"] == "rejected")
            task = req(
                author,
                "POST",
                f"/control-instance-activities/{task['id']}/transition",
                {
                    "expected_version": task["row_version"],
                    "target_status": "under_review",
                    "decision": marker,
                },
            )
            task = req(
                author,
                "POST",
                f"/control-instance-activities/{task['id']}/transition",
                {
                    "expected_version": task["row_version"],
                    "target_status": "completed",
                    "decision": marker,
                    "completion_summary": marker,
                },
            )
            ok("QA task completed", task["status"] == "completed")
            control = req(
                author,
                "POST",
                f"/controls/{control['id']}/retire",
                {"expected_version": control["row_version"]},
            )
            ok("control retired", control["state"] == "retired")
            stage = "audit planning"
            program = req(
                author,
                "POST",
                "/internal-audits/programs",
                {
                    "unit_id": unit["id"],
                    "code": "LAB-QA-AP-" + suffix,
                    "name": "DEMO QA programa",
                    "date_start": today.isoformat(),
                    "date_end": deadline,
                },
            )
            program = req(
                author,
                "PATCH",
                f"/internal-audits/programs/{program['id']}",
                {
                    "expected_version": program["row_version"],
                    "name": "DEMO QA programa editado",
                },
            )
            ok("audit program create/edit", program["name"].endswith("editado"))
            audit = req(
                author,
                "POST",
                "/internal-audits/audits",
                {
                    "unit_id": unit["id"],
                    "program_id": program["id"],
                    "code": "LAB-QA-A-" + suffix,
                    "name": "DEMO QA auditoría",
                    "planned_start": today.isoformat(),
                    "planned_end": deadline,
                    "objective": marker,
                },
            )
            base = f"/internal-audits/audits/{audit['id']}"
            audit = req(
                author,
                "PATCH",
                base,
                {
                    "expected_version": audit["row_version"],
                    "objective": marker + " Editada.",
                },
            )
            ok("audit create/edit", audit["objective"].endswith("Editada."))
            boundary = req(
                author,
                "POST",
                base + "/scopes",
                {
                    "expected_audit_version": audit["row_version"],
                    "sequence": 10,
                    "title": "DEMO QA alcance",
                    "process_id": process["id"],
                },
            )
            boundary = req(
                author,
                "PATCH",
                base + f"/scopes/{boundary['scope']['id']}",
                {
                    "expected_audit_version": boundary["audit_version"],
                    "expected_version": boundary["scope"]["row_version"],
                    "title": "DEMO QA alcance editado",
                },
            )
            ok(
                "audit scope create/edit",
                boundary["scope"]["title"].endswith("editado"),
            )
            boundary = req(
                author,
                "POST",
                base + f"/scopes/{boundary['scope']['id']}/withdraw",
                {
                    "expected_audit_version": boundary["audit_version"],
                    "expected_version": boundary["scope"]["row_version"],
                    "reason": marker,
                },
            )
            ok("audit scope withdraw", boundary["scope"]["status"] == "withdrawn")
            audit = req(author, "GET", base)
            audit = req(
                reviewer,
                "POST",
                base + "/transition",
                {
                    "expected_version": audit["row_version"],
                    "target_state": "cancelled",
                    "decision": marker,
                },
            )
            ok("audit cancel", audit["state"] == "cancelled")
            program = req(
                reviewer,
                "POST",
                f"/internal-audits/programs/{program['id']}/transition",
                {
                    "expected_version": program["row_version"],
                    "target_state": "cancelled",
                    "decision": marker,
                },
            )
            ok("audit program cancel", program["state"] == "cancelled")
            stage = "workflow"
            wf = req(
                owner,
                "POST",
                "/workflows",
                {"code": "LAB-QA-W-" + suffix, "name": "DEMO QA workflow"},
            )
            wf = req(
                owner,
                "PATCH",
                f"/workflows/{wf['id']}",
                {"name": "DEMO QA workflow editado"},
            )
            ok("workflow create/edit", wf["name"].endswith("editado"))
            wf = req(owner, "PATCH", f"/workflows/{wf['id']}", {"status": "retired"})
            ok("workflow retire", wf["status"] == "retired")
            stage = "tenant isolation"
            identity["login"](
                foreign, "pmc-user-b", str(env["KEYCLOAK_USER_B_PASSWORD"])
            )
            tenants = foreign.get(API + "/auth/tenants").json()
            tid = next(x["id"] for x in tenants if x["slug"] == "tenant-b")
            response = identity["post"](
                foreign, API + "/auth/tenant", {"tenant_id": tid}
            )
            ok("select independent company", response.status_code == 200)
            for path in [
                f"/processes/{process['id']}",
                f"/risks/{risk['id']}",
                f"/nonconformities/{n['id']}",
                f"/capas/{c['id']}",
                f"/controls/{control['id']}",
                base,
            ]:
                ok(
                    "cross-company denial " + path.split("/")[1],
                    foreign.get(API + path).status_code == 404,
                )
            stage = "audit trail"
            trail = req(owner, "GET", "/audit/events", params={"limit": 100})
            ok("audit events retained", bool(trail["items"]))
            report = {
                "status": "PASS",
                "checks": checks,
                "check_count": len(checks),
                "run_suffix": suffix,
                "runtime_schema": "not inspected by this API harness; verify deployment inventory separately",
                "writes": "only new synthetic QA records and one temporary grant revoked; no deletion",
                "limitations": "API round trips, not all UI buttons or Odoo parity. QA records retained with history.",
            }
            print(json.dumps(report))
        except Exception as e:  # noqa: BLE001 -- never expose auth bodies
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "stage": stage,
                        "exception": type(e).__name__,
                        "safe_message": str(e)
                        if isinstance(e, D["DemoFailure"])
                        else None,
                        "passed_checks": checks,
                    }
                )
            )
            raise SystemExit(1)
        finally:
            for c in clients:
                if "pm_csrf" in c.cookies:
                    try:
                        c.post(API + "/auth/logout", headers=identity["csrf"](c))
                    except httpx.HTTPError:
                        pass


if __name__ == "__main__":
    main()
