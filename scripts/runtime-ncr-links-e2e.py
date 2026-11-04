"""Validate NCR related records using local OIDC and a real scanned document."""

from __future__ import annotations

import hashlib
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import dotenv_values

_identity = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API, WEB = _identity["API"], _identity["WEB"]
login, csrf, select_tenant, post = (
    _identity[name] for name in ("login", "csrf", "select_tenant", "post")
)
phase = "startup"


def checked(response: httpx.Response, status: int = 200) -> dict[str, Any]:
    if response.status_code != status:
        raise AssertionError(f"unexpected HTTP status {response.status_code}")
    return response.json()


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("NCR links E2E requires local development environment")
    grants: list[str] = []
    document: dict[str, Any] | None = None
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
            phase = "temporary explicit responsibilities"
            for prefix, capabilities in (
                (
                    "pmc-user-a",
                    (
                        "processes.read",
                        "ncr.read",
                        "ncr.manage",
                        "risks.read",
                        "risks.manage",
                        "controls.read",
                        "controls.manage",
                        "control_instances.read",
                        "control_instances.manage",
                        "documents.read",
                        "documents.author",
                    ),
                ),
                (
                    "pmc-multi-user",
                    (
                        "ncr.read",
                        "ncr.review",
                        "risks.read",
                        "risks.review",
                        "control_instances.read",
                        "control_instances.manage",
                        "documents.read",
                        "documents.review",
                        "documents.approve",
                        "documents.release",
                        "documents.obsolete",
                    ),
                ),
            ):
                for capability in capabilities:
                    if (users[prefix], unit["id"], capability) in active:
                        continue
                    grant = checked(
                        post(
                            owner,
                            f"{API}/qms-access/grants",
                            {
                                "user_id": users[prefix],
                                "unit_id": unit["id"],
                                "capability": capability,
                            },
                        ),
                        201,
                    )
                    grants.append(grant["id"])
            process = next(
                r
                for r in author.get(
                    f"{API}/processes", params={"unit_id": unit["id"]}
                ).json()
                if r["status"] == "active"
            )
            suffix = uuid4().hex[:10].upper()
            scope = {"unit_id": unit["id"], "process_id": process["id"]}
            phase = "historical closed risk target"
            risk = checked(
                post(
                    author,
                    f"{API}/risks",
                    {
                        **scope,
                        "code": f"DEV-E2E-NRL-R-{suffix}",
                        "name": "Fictional distribution risk",
                        "description": "Local validation of an NCR reference to a historical risk.",
                        "response_strategy": "mitigate",
                        "mitigation_plan": "Validate linked records.",
                    },
                ),
                201,
            )
            for state in ("assessed", "monitoring", "closed"):
                risk = checked(
                    post(
                        reviewer,
                        f"{API}/risks/{risk['id']}/transition",
                        {
                            "expected_version": risk["row_version"],
                            "target_state": state,
                            "decision": "Fictional local risk review.",
                            **(
                                {
                                    "closure_notes": "Synthetic historical reference retained."
                                }
                                if state == "closed"
                                else {}
                            ),
                        },
                    )
                )
            phase = "active control implementation target"
            control = checked(
                post(
                    author,
                    f"{API}/controls",
                    {
                        **scope,
                        "code": f"DEV-E2E-NRL-C-{suffix}",
                        "name": "Fictional distribution check",
                        "objective": "Validate NCR related implementation traceability.",
                    },
                ),
                201,
            )
            requirement = checked(
                post(
                    author,
                    f"{API}/controls/{control['id']}/evidence-requirements",
                    {
                        "name": "Fictional reviewed receiving record",
                        "evidence_type": "record",
                        "mandatory": True,
                    },
                ),
                201,
            )
            checked(
                post(
                    author,
                    f"{API}/controls/{control['id']}/activate",
                    {
                        "expected_version": control["row_version"],
                    },
                )
            )
            instance = checked(
                post(
                    author,
                    f"{API}/control-instances?unit_id={unit['id']}&process_id={process['id']}",
                    {
                        "control_id": control["id"],
                        "code": f"DEV-E2E-NRL-I-{suffix}",
                        "name": "Fictional NCR implementation reference",
                    },
                ),
                201,
            )
            phase = "independent review of implementation evidence"
            evidence = next(
                r
                for r in author.get(
                    f"{API}/control-instance-evidence",
                    params={
                        "instance_id": instance["id"],
                    },
                ).json()
                if r["requirement_definition_id"] == requirement["id"]
            )
            evidence = checked(
                author.patch(
                    f"{API}/control-instance-evidence/{evidence['id']}",
                    json={
                        "expected_version": evidence["row_version"],
                        "evidence_summary": "Fictional receiving outcome reviewed.",
                    },
                    headers=csrf(author),
                )
            )
            evidence = checked(
                post(
                    author,
                    f"{API}/control-instance-evidence/{evidence['id']}/submit",
                    {
                        "expected_version": evidence["row_version"],
                    },
                )
            )
            evidence = checked(
                post(
                    reviewer,
                    f"{API}/control-instance-evidence/{evidence['id']}/review",
                    {
                        "expected_version": evidence["row_version"],
                        "target_status": "accepted",
                        "decision": "Fictional independent review accepted.",
                    },
                )
            )
            if (
                evidence["status"] != "accepted"
                or evidence["reviewed_by_user_id"] == evidence["submitted_by_user_id"]
            ):
                raise AssertionError("evidence acceptance lacked independent review")
            phase = "release independently reviewed scanned PDF target"
            document = checked(
                post(
                    author,
                    f"{API}/documents",
                    {
                        **scope,
                        "code": f"DEV-E2E-NRL-D-{suffix}",
                        "title": "Fictional NCR controlled record",
                        "document_type": "procedure",
                        "owner_user_id": users["pmc-user-a"],
                    },
                ),
                201,
            )
            revision = checked(
                post(
                    author,
                    f"{API}/documents/{document['id']}/revisions",
                    {
                        "revision": "1.0",
                        "change_summary": "Synthetic NCR link validation.",
                        "revision_date": datetime.now(UTC).date().isoformat(),
                    },
                ),
                201,
            )
            pdf = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
            uploaded = checked(
                author.put(
                    f"{API}/documents/{document['id']}/revisions/{revision['id']}/file",
                    content=pdf,
                    headers={**csrf(author), "Content-Type": "application/pdf"},
                ),
                202,
            )
            if uploaded.get("file_state") != "clean":
                raise AssertionError("synthetic PDF did not pass real antivirus scan")
            revision = next(
                r
                for r in author.get(
                    f"{API}/documents/{document['id']}/revisions"
                ).json()
                if r["id"] == revision["id"]
            )
            for command in ("submit", "approve", "release"):
                revision = checked(
                    post(
                        reviewer,
                        f"{API}/documents/{document['id']}/revisions/{revision['id']}/{command}",
                        {"expected_version": revision["row_version"]},
                    )
                )
            phase = "NCR creation and related snapshots"
            ncr = checked(
                post(
                    author,
                    f"{API}/nonconformities",
                    {
                        **scope,
                        "code": f"DEV-E2E-NRL-{suffix}",
                        "name": "Fictional related-record validation",
                        "source_type": "document",
                        "description": "Synthetic NCR link validation only.",
                    },
                ),
                201,
            )
            base = f"{API}/nonconformities/{ncr['id']}"
            links: dict[str, dict[str, Any]] = {}
            payloads = {
                "risk": {"risk_id": risk["id"]},
                "control": {"control_instance_id": instance["id"]},
                "evidence": {"evidence_id": evidence["id"]},
                "document": {
                    "document_id": document["id"],
                    "document_revision_id": revision["id"],
                },
            }
            for kind, values in payloads.items():
                linked = checked(
                    post(
                        author,
                        f"{WEB}/api/identity/nonconformities/{ncr['id']}/{kind}-links",
                        {
                            "expected_version": ncr["row_version"],
                            **values,
                        },
                    ),
                    201,
                )
                if linked["ncr_row_version"] != ncr["row_version"] + 1:
                    raise AssertionError(
                        "NCR parent version did not advance with its link"
                    )
                ncr["row_version"] = linked["ncr_row_version"]
                links[kind] = linked
            if links["risk"]["target_state"] != "closed":
                raise AssertionError(
                    "historical risk state missing from linked reference"
                )
            if links["document"]["file_sha256"] != hashlib.sha256(pdf).hexdigest():
                raise AssertionError(
                    "NCR document snapshot did not retain the scanned file hash"
                )
            phase = "permission denial and conflict recovery"
            if reviewer.get(f"{base}/control-links").status_code != 200:
                raise AssertionError(
                    "authorized reviewer could not read related controls"
                )
            if (
                post(
                    reviewer,
                    f"{base}/risk-links",
                    {
                        "expected_version": ncr["row_version"],
                        "risk_id": risk["id"],
                    },
                ).status_code
                != 403
            ):
                raise AssertionError("NCR reviewer received implicit manage authority")
            if owner.get(f"{base}/risk-links").status_code not in {403, 404}:
                raise AssertionError(
                    "tenant owner received implicit NCR related-record access"
                )
            if (
                post(
                    author,
                    f"{base}/risk-links",
                    {
                        "expected_version": 1,
                        "risk_id": risk["id"],
                    },
                ).status_code
                != 409
            ):
                raise AssertionError("stale related-record command was accepted")
            phase = "soft removal and independent historical relink"
            removed = checked(
                post(
                    author,
                    f"{base}/control-links/{links['control']['id']}/remove",
                    {
                        "expected_version": ncr["row_version"],
                        "expected_link_version": 1,
                        "reason": "Replace synthetic reference after validation.",
                    },
                )
            )
            ncr["row_version"] = removed["ncr_row_version"]
            if removed["status"] != "removed" or not removed["removed_at"]:
                raise AssertionError("link removal erased traceability")
            replacement = checked(
                post(
                    author,
                    f"{base}/control-links",
                    {
                        "expected_version": ncr["row_version"],
                        "control_instance_id": instance["id"],
                    },
                ),
                201,
            )
            ncr["row_version"] = replacement["ncr_row_version"]
            history = author.get(f"{base}/control-links").json()
            if len(history) != 2 or {r["status"] for r in history} != {
                "active",
                "removed",
            }:
                raise AssertionError(
                    "NCR link history did not preserve removed and replacement records"
                )
            phase = "controlled closure with preserved references"
            for state in ("open", "investigation", "action_required", "closed"):
                ncr = checked(
                    post(
                        author if state == "open" else reviewer,
                        f"{base}/transition",
                        {
                            "expected_version": ncr["row_version"],
                            "target_state": state,
                            "decision": "Fictional local NCR related-record verification.",
                            **(
                                {
                                    "closure_notes": "Synthetic references checked and retained."
                                }
                                if state == "closed"
                                else {}
                            ),
                        },
                    )
                )
            if (
                post(
                    author,
                    f"{base}/risk-links/{links['risk']['id']}/remove",
                    {
                        "expected_version": ncr["row_version"],
                        "expected_link_version": 1,
                        "reason": "Attempt terminal rewrite.",
                    },
                ).status_code
                != 409
            ):
                raise AssertionError("closed NCR relationships could be rewritten")
            phase = "document obsolescence with snapshot preserved"
            current_documents = author.get(
                f"{API}/documents",
                params={
                    "unit_id": unit["id"],
                    "search": document["code"],
                },
            ).json()
            current_document = next(
                r for r in current_documents if r["id"] == document["id"]
            )
            document = checked(
                post(
                    reviewer,
                    f"{API}/documents/{document['id']}/obsolete",
                    {
                        "expected_version": current_document["row_version"],
                    },
                )
            )
            retained = author.get(
                f"{WEB}/api/identity/nonconformities/{ncr['id']}/document-links"
            )
            if (
                retained.status_code != 200
                or retained.json()[0]["target_state"] != "obsolete"
            ):
                raise AssertionError("obsoleted target lost NCR historical reference")
            if retained.json()[0]["snapshot_revision"] != "1.0":
                raise AssertionError("NCR released revision snapshot changed")
            phase = "related-record audit evidence"
            events = owner.get(f"{API}/audit/events?limit=100").json()["items"]
            ids = {row["id"] for row in links.values()} | {replacement["id"]}
            relevant = [r for r in events if r["resource_id"] in ids]
            if not {
                "ncr.risk_linked",
                "ncr.control_linked",
                "ncr.document_linked",
                "ncr.control_unlinked",
                "ncr.evidence_linked",
            } <= {r["action"] for r in relevant}:
                raise AssertionError("NCR relationship audit history incomplete")
        finally:
            if document is not None and document.get("status") != "obsolete":
                try:
                    rows = author.get(
                        f"{API}/documents",
                        params={
                            "unit_id": document["unit_id"],
                            "search": document["code"],
                        },
                    ).json()
                    current_document = next(
                        r for r in rows if r["id"] == document["id"]
                    )
                    cleanup_failed |= (
                        post(
                            reviewer,
                            f"{API}/documents/{document['id']}/obsolete",
                            {
                                "expected_version": current_document["row_version"],
                            },
                        ).status_code
                        != 200
                    )
                except Exception:  # noqa: BLE001 -- attempt all cleanup without leaking credentials
                    cleanup_failed = True
            for grant_id in reversed(grants):
                try:
                    cleanup_failed |= (
                        post(
                            owner, f"{API}/qms-access/grants/{grant_id}/revoke", {}
                        ).status_code
                        != 200
                    )
                except Exception:  # noqa: BLE001 -- finish remaining grant cleanup
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
                    except Exception:  # noqa: BLE001 -- finish closing synthetic sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError(
                    "NCR links E2E grants/session cleanup could not be verified"
                )
    print(
        "OIDC, NCR risks/controls/accepted evidence/scanned PDF, history, permissions and proxy: PASS"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- redact auth URLs, tokens and credentials
        raise SystemExit(
            f"NCR links E2E failed during {phase} ({type(error).__name__}); credentials redacted."
        ) from None
