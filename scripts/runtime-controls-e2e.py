"""Exercise the control catalog through local OIDC, API and same-origin web proxy."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import dotenv_values

API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"
CAPABILITIES = (
    "processes.read",
    "controls.read",
    "controls.manage",
    "control_instances.read",
    "control_instances.manage",
    "documents.author",
    "documents.read",
    "risks.read", "risks.manage",
)
REVIEW_CAPABILITIES = (
    "controls.read", "control_instances.read", "control_instances.manage",
    "documents.read", "documents.review", "documents.approve",
    "documents.release", "documents.obsolete",
    "risks.read", "risks.review",
)
phase = "startup"


class LoginForm(HTMLParser):
    action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


def csrf(client: httpx.Client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["pm_csrf"]}


def login(client: httpx.Client, username: str, password: str) -> None:
    page = client.get(f"{API}/auth/login")
    page.raise_for_status()
    form = LoginForm()
    form.feed(page.text)
    if form.action is None:
        raise AssertionError("local identity login form unavailable")
    target = urlparse(form.action)
    if (target.scheme, target.netloc) != ("http", "127.0.0.1:8080"):
        raise RuntimeError("refusing credentials outside the local identity provider")
    for cookie in client.cookies.jar:
        if cookie.domain == "127.0.0.1" and cookie.path == "/realms/perfect-match/":
            cookie.secure = False
    response = client.post(
        form.action, data={"username": username, "password": password}
    )
    if not response.is_success or client.get(f"{API}/auth/me").status_code != 200:
        raise AssertionError("local OIDC login failed")


def select_tenant(client: httpx.Client) -> str:
    tenants = client.get(f"{API}/auth/tenants").json()
    tenant_id = next((row["id"] for row in tenants if row["slug"] == "tenant-a"), None)
    if tenant_id is None:
        raise AssertionError("development tenant unavailable")
    response = client.post(
        f"{API}/auth/tenant", json={"tenant_id": tenant_id}, headers=csrf(client)
    )
    if response.status_code != 200:
        raise AssertionError("could not select development tenant")
    return tenant_id


def post(client: httpx.Client, path: str, body: dict[str, object]) -> httpx.Response:
    return client.post(path, json=body, headers=csrf(client))


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("control E2E requires local development environment")

    grant_ids: list[str] = []
    document_id: str | None = None
    document_code: str | None = None
    cleanup_failed = False
    with ExitStack() as stack:
        owner = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        member = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        reviewer = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        clients = (owner, member, reviewer)
        try:
            phase = "OIDC login and tenant selection"
            phase = "owner OIDC login"
            login(owner, "pmc-local-owner", str(env["KEYCLOAK_OWNER_PASSWORD"]))
            phase = "submitter OIDC login"
            login(member, "pmc-user-a", str(env["KEYCLOAK_USER_A_PASSWORD"]))
            phase = "reviewer OIDC login"
            login(reviewer, "pmc-multi-user", str(env["KEYCLOAK_MULTI_USER_PASSWORD"]))
            phase = "tenant selection"
            owner_tenant = select_tenant(owner)
            member_tenant = select_tenant(member)
            reviewer_tenant = select_tenant(reviewer)
            if owner_tenant != member_tenant or owner_tenant != reviewer_tenant:
                raise AssertionError("tenant isolation setup does not match")

            members = owner.get(f"{API}/organization/members?limit=100").json()
            member_id = next(
                (
                    row["id"]
                    for row in members
                    if row["display_name"].startswith("pmc-user-a")
                ),
                None,
            )
            reviewer_id = next(
                (row["id"] for row in members if row["display_name"].startswith("pmc-multi-user")),
                None,
            )
            units = owner.get(f"{API}/organization/units?limit=100").json()
            unit = next(
                (
                    row
                    for row in units
                    if row["code"] == "DEV-ACCESS-UI" and row["status"] == "active"
                ),
                None,
            )
            if not member_id or not reviewer_id or unit is None:
                raise AssertionError("development member or QMS scope unavailable")

            existing = owner.get(f"{API}/qms-access/grants").json()
            active = {
                (row["user_id"], row["unit_id"], row["capability"])
                for row in existing
                if row["status"] == "active"
            }
            for capability in CAPABILITIES:
                if (member_id, unit["id"], capability) in active:
                    continue
                response = post(
                    owner,
                    f"{API}/qms-access/grants",
                    {
                        "user_id": member_id,
                        "unit_id": unit["id"],
                        "capability": capability,
                    },
                )
                if response.status_code != 201:
                    raise AssertionError(
                        "could not grant temporary control capabilities"
                    )
                grant_ids.append(response.json()["id"])
            reviewer_active = {
                (row["user_id"], row["unit_id"], row["capability"])
                for row in existing
                if row["status"] == "active"
            }
            for capability in REVIEW_CAPABILITIES:
                if (reviewer_id, unit["id"], capability) in reviewer_active:
                    continue
                response = post(owner, f"{API}/qms-access/grants", {
                    "user_id": reviewer_id, "unit_id": unit["id"], "capability": capability,
                })
                if response.status_code != 201:
                    raise AssertionError("could not grant temporary evidence reviewer capabilities")
                grant_ids.append(response.json()["id"])

            processes = member.get(
                f"{API}/processes?unit_id={unit['id']}&limit=100"
            ).json()
            process = next(
                (row for row in processes if row["status"] == "active"), None
            )
            if process is None:
                raise AssertionError("active development process unavailable")

            suffix = uuid4().hex[:10]
            phase = "control draft creation"
            created = post(
                member,
                f"{API}/controls",
                {
                    "unit_id": unit["id"],
                    "process_id": process["id"],
                    "code": f"DEV-E2E-CTL-{suffix}",
                    "name": "Local control workflow verification",
                    "objective": "Verify tenant-scoped control implementation workflow",
                    "category": "process",
                },
            )
            if created.status_code != 201:
                raise AssertionError("control creation failed")
            control = created.json()
            phase = "implementation activity definition"
            activity_response = post(
                member,
                f"{API}/controls/{control['id']}/activities",
                {
                    "name": "Review supplier performance",
                    "activity_kind": "qms_implementation",
                    "readiness_required": True,
                    "objective": "Record the recurring review outcome",
                    "expected_output": "Approved supplier review record",
                },
            )
            if activity_response.is_error:
                detail = activity_response.json().get("detail", "no response detail")
                phase = f"implementation activity response HTTP {activity_response.status_code}: {detail}"
            if activity_response.status_code != 201:
                raise AssertionError(
                    f"implementation activity create returned HTTP {activity_response.status_code}"
                )
            activity = activity_response.json()
            if not activity["readiness_required"]:
                raise AssertionError("implementation activity should count for readiness")
            phase = "evidence requirement definition"
            requirement_response = post(
                member,
                f"{API}/controls/{control['id']}/evidence-requirements",
                {
                    "name": "Supplier review evidence",
                    "description": "Approved review outcome and follow-up actions.",
                    "acceptance_criteria": "The review has approval and assigned owners.",
                    "evidence_type": "document",
                    "mandatory": True,
                },
            )
            if requirement_response.status_code != 201:
                raise AssertionError("control evidence requirement was not saved")
            phase = "create and release evidence document revision"
            document_code = f"DEV-E2E-EVID-{suffix}"
            phase = "create evidence source document"
            document_response = post(member, f"{API}/documents", {
                "unit_id": unit["id"], "process_id": process["id"],
                "code": document_code, "title": "Evidence link verification",
                "document_type": "procedure", "owner_user_id": member_id,
            })
            if document_response.status_code != 201:
                raise AssertionError(f"evidence source document creation failed (HTTP {document_response.status_code})")
            evidence_document = document_response.json()
            document_id = evidence_document["id"]
            phase = "create evidence source revision"
            revision_response = post(member, f"{API}/documents/{document_id}/revisions", {
                "revision": "1.0", "change_summary": "E2E controlled evidence source",
                "revision_date": datetime.now(UTC).date().isoformat(),
            })
            if revision_response.status_code != 201:
                raise AssertionError(f"evidence source revision creation failed (HTTP {revision_response.status_code})")
            revision = revision_response.json()
            pdf = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
            phase = "scan and store evidence source PDF"
            upload = member.put(
                f"{API}/documents/{document_id}/revisions/{revision['id']}/file",
                content=pdf, headers={**csrf(member), "Content-Type": "application/pdf"},
            )
            if upload.status_code != 202 or upload.json().get("file_state") != "clean":
                raise AssertionError(f"evidence document scan/storage failed (HTTP {upload.status_code})")
            phase = "submit evidence source revision"
            submitted_revision = post(reviewer,
                f"{API}/documents/{document_id}/revisions/{revision['id']}/submit",
                {"expected_version": upload.json().get("row_version", revision["row_version"] + 1)})
            if submitted_revision.status_code != 200:
                detail = submitted_revision.json().get("detail", "no response detail")
                raise AssertionError(f"evidence source revision submission failed: {detail}")
            phase = "approve evidence source revision"
            approved_revision = post(reviewer,
                f"{API}/documents/{document_id}/revisions/{revision['id']}/approve",
                {"expected_version": submitted_revision.json()["row_version"]})
            if approved_revision.status_code != 200:
                detail = approved_revision.json().get("detail", "no response detail")
                raise AssertionError(f"evidence source revision approval failed: {detail}")
            phase = "release evidence source revision"
            released_revision = post(reviewer,
                f"{API}/documents/{document_id}/revisions/{revision['id']}/release",
                {"expected_version": approved_revision.json()["row_version"]})
            if released_revision.status_code != 200 or released_revision.json()["status"] != "active":
                detail = released_revision.json().get("detail", "no response detail")
                raise AssertionError(f"evidence source revision release failed: {detail}")
            phase = "same-origin method definition proxies"
            activity_proxy = member.get(
                f"{WEB}/api/identity/controls/{control['id']}/activities"
            )
            requirement_proxy = member.get(
                f"{WEB}/api/identity/controls/{control['id']}/evidence-requirements"
            )
            if (
                activity_proxy.status_code != 200
                or not any(row["id"] == activity["id"] for row in activity_proxy.json())
                or requirement_proxy.status_code != 200
                or not any(row["id"] == requirement_response.json()["id"] for row in requirement_proxy.json())
            ):
                raise AssertionError("same-origin definition proxies did not return scoped data")
            active_control = post(
                member,
                f"{API}/controls/{control['id']}/activate",
                {"expected_version": control["row_version"]},
            )
            if (
                active_control.status_code != 200
                or active_control.json()["state"] != "active"
            ):
                raise AssertionError("control activation failed")
            phase = "active control definition lock"
            locked_activity = member.patch(
                f"{API}/control-activities/{activity['id']}",
                json={"expected_version": activity["row_version"], "active": False},
                headers=csrf(member),
            )
            if locked_activity.status_code != 409:
                raise AssertionError("active control definitions should be locked")

            phase = "implementation instance workflow"
            instance_response = post(
                member,
                f"{API}/control-instances?unit_id={unit['id']}&process_id={process['id']}",
                {
                    "control_id": control["id"],
                    "code": f"DEV-E2E-IMP-{suffix}",
                    "name": "Local implementation verification",
                },
            )
            if instance_response.status_code != 201:
                raise AssertionError("implementation record creation failed")
            instance = instance_response.json()
            phase = "generated implementation task readiness gate"
            task_path = f"{API}/control-instance-activities?instance_id={instance['id']}"
            tasks_response = member.get(task_path)
            if tasks_response.status_code != 200:
                raise AssertionError("generated implementation activity was not readable")
            tasks = tasks_response.json()
            task = next((row for row in tasks if row["activity_definition_id"] == activity["id"]), None)
            if task is None or task["status"] != "not_started" or not task["readiness_required"]:
                raise AssertionError("implementation task snapshot was not generated")
            task_proxy = member.get(f"{WEB}/api/identity/control-instance-activities",
                                    params={"instance_id": instance["id"]})
            if task_proxy.status_code != 200 or not any(row["id"] == task["id"] for row in task_proxy.json()):
                raise AssertionError("same-origin implementation task proxy failed")
            blocked = post(member, f"{API}/control-instances/{instance['id']}/transition", {
                "expected_version": instance["row_version"], "target_status": "in_progress",
                "decision": "Development implementation started",
            })
            if blocked.status_code != 200:
                raise AssertionError("implementation should enter in-progress before readiness is checked")
            instance = blocked.json()
            blocked = post(member, f"{API}/control-instances/{instance['id']}/transition", {
                "expected_version": instance["row_version"], "target_status": "under_review",
                "decision": "Attempt before required task completion",
            })
            if blocked.status_code != 409:
                raise AssertionError("readiness gate allowed review before task completion")
            for target, decision, summary in (
                ("in_progress", "Task work started", ""),
                ("under_review", "Task submitted", ""),
                ("completed", "Task verified", "Supplier review evidence was checked."),
            ):
                response = post(member, f"{API}/control-instance-activities/{task['id']}/transition", {
                    "expected_version": task["row_version"], "target_status": target,
                    "decision": decision, "completion_summary": summary,
                })
                if response.status_code != 200:
                    raise AssertionError(f"implementation activity transition failed: {target}")
                task = response.json()
            phase = "evidence submission and independent review"
            evidence_response = member.get(
                f"{API}/control-instance-evidence?instance_id={instance['id']}"
            )
            if evidence_response.status_code != 200:
                raise AssertionError("implementation evidence checklist was not generated")
            evidence = evidence_response.json()
            item = next((row for row in evidence if row["requirement_definition_id"] == requirement_response.json()["id"]), None)
            if item is None or item["status"] != "draft":
                raise AssertionError("evidence requirement snapshot was not generated")
            evidence_proxy = member.get(
                f"{WEB}/api/identity/control-instance-evidence",
                params={"instance_id": instance["id"]},
            )
            if evidence_proxy.status_code != 200 or not any(
                row["id"] == item["id"] for row in evidence_proxy.json()
            ):
                raise AssertionError("same-origin implementation evidence proxy failed")
            edited = member.patch(
                f"{API}/control-instance-evidence/{item['id']}",
                json={"expected_version": item["row_version"],
                      "evidence_summary": "Supplier review record and approval are filed.",
                      "document_id": document_id,
                      "document_revision_id": released_revision.json()["id"]},
                headers=csrf(member),
            )
            if edited.status_code != 200:
                raise AssertionError("evidence summary and released document link were not saved")
            if edited.json()["document_revision_id"] != released_revision.json()["id"]:
                raise AssertionError("released controlled revision was not linked to the evidence")
            submitted = post(member, f"{API}/control-instance-evidence/{item['id']}/submit",
                             {"expected_version": edited.json()["row_version"]})
            if submitted.status_code != 200:
                raise AssertionError("evidence was not submitted for review")
            self_review = post(member, f"{API}/control-instance-evidence/{item['id']}/review", {
                "expected_version": submitted.json()["row_version"],
                "target_status": "accepted", "decision": "Cannot approve own submission",
            })
            if self_review.status_code != 403:
                raise AssertionError("evidence submitter was allowed to review their own work")
            accepted = post(reviewer, f"{API}/control-instance-evidence/{item['id']}/review", {
                "expected_version": submitted.json()["row_version"],
                "target_status": "accepted", "decision": "Evidence meets the acceptance criteria.",
            })
            if accepted.status_code != 200 or accepted.json()["status"] != "accepted":
                raise AssertionError("independent evidence review did not accept the record")
            for target, decision in (
                ("under_review", "Development implementation submitted"),
                ("implemented", "Development implementation reviewed"),
            ):
                transition = post(
                    member,
                    f"{API}/control-instances/{instance['id']}/transition",
                    {
                        "expected_version": instance["row_version"],
                        "target_status": target,
                        "decision": decision,
                    },
                )
                if transition.status_code != 200:
                    raise AssertionError("implementation transition failed")
                instance = transition.json()
            if (
                instance["implementation_status"] != "implemented"
                or not instance["implementation_date"]
            ):
                raise AssertionError("implementation closure was incomplete")

            phase = "risk links to implementation and released document"
            risk_response = post(member, f"{API}/risks", {
                "unit_id": unit["id"], "process_id": process["id"],
                "code": f"DEV-E2E-LINK-{suffix}", "name": "Supplier continuity exposure",
                "description": "Fictional risk with linked response control and released evidence.",
            })
            if risk_response.status_code != 201:
                raise AssertionError("linked risk creation failed")
            risk = risk_response.json()
            control_link_response = post(member, f"{API}/risks/{risk['id']}/control-links", {
                "expected_version": risk["row_version"], "control_instance_id": instance["id"],
            })
            if control_link_response.status_code != 201:
                raise AssertionError("risk control implementation link failed")
            control_link = control_link_response.json()
            risk["row_version"] = control_link["risk_row_version"]
            document_link_response = post(member, f"{API}/risks/{risk['id']}/document-links", {
                "expected_version": risk["row_version"], "document_id": document_id,
                "document_revision_id": released_revision.json()["id"],
            })
            if document_link_response.status_code != 201:
                raise AssertionError("risk released clean revision link failed")
            document_link = document_link_response.json()
            risk["row_version"] = document_link["risk_row_version"]
            if document_link["file_sha256"] != released_revision.json()["file_sha256"]:
                raise AssertionError("risk document hash snapshot mismatched")
            phase = "risk link removal history and versioning"
            removed_link = post(member, f"{API}/risks/{risk['id']}/control-links/{control_link['id']}/remove", {
                "expected_version": risk["row_version"], "expected_link_version": control_link["row_version"],
                "reason": "Development validation preserves the removed relationship.",
            })
            if removed_link.status_code != 200 or removed_link.json()["status"] != "removed":
                raise AssertionError("risk link soft removal failed")
            risk["row_version"] = removed_link.json()["risk_row_version"]
            link_proxy = member.get(f"{WEB}/api/identity/risks/{risk['id']}/document-links")
            if link_proxy.status_code != 200 or not any(row["id"] == document_link["id"] for row in link_proxy.json()):
                raise AssertionError("same-origin risk links proxy failed")
            for target in ("assessed", "monitoring", "closed"):
                decision = {"expected_version": risk["row_version"], "target_state": target,
                            "decision": "Fictional linked-risk review completed."}
                if target == "closed":
                    decision["closure_notes"] = "Local validation completed with references preserved."
                result = post(reviewer, f"{API}/risks/{risk['id']}/transition", decision)
                if result.status_code != 200:
                    raise AssertionError("linked risk workflow failed")
                risk = result.json()

            phase = "control list proxy"
            proxy = member.get(
                f"{WEB}/api/identity/controls",
                params={"unit_id": unit["id"], "process_id": process["id"]},
            )
            if proxy.status_code != 200 or not any(
                row["id"] == control["id"] for row in proxy.json()
            ):
                raise AssertionError(
                    "same-origin controls proxy did not return the scoped control"
                )

            phase = "control retirement and audit"
            retired = post(
                member,
                f"{API}/controls/{control['id']}/retire",
                {"expected_version": active_control.json()["row_version"]},
            )
            if retired.status_code != 200 or retired.json()["state"] != "retired":
                raise AssertionError("control retirement failed")
            events = owner.get(f"{API}/audit/events?limit=100").json()["items"]
            actions = {event["action"] for event in events}
            if (
                not {
                    "control.created",
                    "control.activated",
                    "control.activity_created",
                    "control.evidence_requirement_created",
                    "control_instance_activity.created",
                    "control_instance_activity.transitioned",
                    "control_instance_evidence.created",
                    "control_instance_evidence.submitted",
                    "control_instance_evidence.accepted",
                    "control_instance.transitioned",
                    "control.retired",
                }
                <= actions
            ):
                raise AssertionError("control workflow audit events are incomplete")
            phase = "obsolete temporary evidence document"
            document_rows = member.get(
                f"{API}/documents?unit_id={unit['id']}&limit=100&search={document_code}"
            ).json()
            source_document = next(
                (row for row in document_rows if row["id"] == document_id), None
            )
            if source_document is None:
                raise AssertionError("temporary evidence document could not be found for cleanup")
            obsoleted = post(reviewer, f"{API}/documents/{document_id}/obsolete", {
                "expected_version": source_document["row_version"],
            })
            if obsoleted.status_code != 200:
                raise AssertionError("temporary evidence document could not be obsoleted")
            historical = member.get(f"{API}/risks/{risk['id']}/document-links")
            if historical.status_code != 200 or not any(
                row["id"] == document_link["id"] and row["target_state"] == "obsolete"
                for row in historical.json()
            ):
                raise AssertionError("historical document reference was not preserved")
        finally:
            for grant_id in reversed(grant_ids):
                try:
                    response = owner.post(
                        f"{API}/qms-access/grants/{grant_id}/revoke",
                        headers=csrf(owner),
                    )
                    cleanup_failed |= not response.is_success
                except Exception:  # noqa: BLE001 -- cleanup must not expose credentials
                    cleanup_failed = True
            for client in clients:
                if "pm_csrf" in client.cookies:
                    try:
                        response = client.post(
                            f"{API}/auth/logout", headers=csrf(client)
                        )
                        cleanup_failed |= response.status_code != 204
                    except Exception:  # noqa: BLE001 -- close remaining local test sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError(
                    "temporary grant or local session cleanup could not be verified"
                )
    print(
        "OIDC, controls/evidence, risk links, document history, audit and web proxy: PASS"
    )


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(
            f"Control E2E failed during {phase}: {error}. Credentials redacted."
        ) from None
    except Exception as error:  # noqa: BLE001 -- avoid displaying local URLs, credentials or tokens
        raise SystemExit(
            f"Control E2E failed during {phase} ({type(error).__name__}); inspect local services. Credentials redacted."
        ) from None
