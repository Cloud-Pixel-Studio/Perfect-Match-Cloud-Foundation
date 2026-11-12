"""Validate CAPA released document citations through local OIDC and web proxy."""

from __future__ import annotations

import hashlib
from contextlib import ExitStack
from datetime import UTC, datetime
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


def checked(response: httpx.Response, status: int = 200) -> dict[str, object]:
    if response.status_code != status:
        raise AssertionError(f"unexpected HTTP status {response.status_code}")
    return response.json()


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("CAPA document E2E requires local development environment")
    grants: list[str] = []
    document: dict[str, object] | None = None
    cleanup_failed = False
    with ExitStack() as stack:
        owner, author, reviewer = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(3)
        )
        clients = (owner, author, reviewer)
        try:
            phase = "OIDC sessions and tenant selection"
            for client, username, key in (
                (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
                (author, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
                (reviewer, "pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
            ):
                login(client, username, str(env[key]))
                select_tenant(client)
            members = checked(owner.get(f"{API}/organization/members?limit=100"))
            ids = {
                prefix: next(
                    row["id"] for row in members
                    if row["display_name"].startswith(prefix)
                ) for prefix in ("pmc-user-a", "pmc-multi-user")
            }
            units = checked(owner.get(f"{API}/organization/units?limit=100"))
            unit = next(
                row for row in units
                if row["code"] == "DEV-ACCESS-UI" and row["status"] == "active"
            )
            existing = {
                (row["user_id"], row["unit_id"], row["capability"])
                for row in checked(owner.get(f"{API}/qms-access/grants"))
                if row["status"] == "active"
            }
            phase = "temporary explicit capabilities"
            for prefix, capabilities in (
                ("pmc-user-a", (
                    "processes.read", "capa.read", "capa.manage",
                    "documents.read", "documents.author",
                )),
                ("pmc-multi-user", (
                    "documents.read", "documents.review", "documents.approve",
                    "documents.release", "documents.obsolete",
                )),
            ):
                for capability in capabilities:
                    if (ids[prefix], unit["id"], capability) in existing:
                        continue
                    grant = checked(post(owner, f"{API}/qms-access/grants", {
                        "user_id": ids[prefix], "unit_id": unit["id"],
                        "capability": capability,
                    }), 201)
                    grants.append(grant["id"])
            process = next(
                row for row in checked(author.get(
                    f"{API}/processes", params={"unit_id": unit["id"]},
                )) if row["status"] == "active"
            )
            suffix = uuid4().hex[:10].upper()
            scope = {"unit_id": unit["id"], "process_id": process["id"]}
            phase = "scanned and independently released document revision"
            document = checked(post(author, f"{API}/documents", {
                **scope, "code": f"DEV-E2E-CDL-D-{suffix}",
                "title": "Fictional CAPA controlled reference",
                "document_type": "procedure", "owner_user_id": ids["pmc-user-a"],
            }), 201)
            revision = checked(post(author, f"{API}/documents/{document['id']}/revisions", {
                "revision": "1.0", "change_summary": "Synthetic CAPA citation validation.",
                "revision_date": datetime.now(UTC).date().isoformat(),
            }), 201)
            pdf = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
            uploaded = checked(author.put(
                f"{API}/documents/{document['id']}/revisions/{revision['id']}/file",
                content=pdf, headers={**csrf(author), "Content-Type": "application/pdf"},
            ), 202)
            if uploaded["file_state"] != "clean":
                raise AssertionError("PDF failed real antivirus scan")
            revision = next(
                row for row in checked(author.get(f"{API}/documents/{document['id']}/revisions"))
                if row["id"] == revision["id"]
            )
            for command in ("submit", "approve", "release"):
                revision = checked(post(
                    reviewer,
                    f"{API}/documents/{document['id']}/revisions/{revision['id']}/{command}",
                    {"expected_version": revision["row_version"]},
                ))
            phase = "scoped CAPA and linked snapshot through web proxy"
            capa = checked(post(author, f"{API}/capas", {
                **scope, "code": f"DEV-E2E-CDL-C-{suffix}",
                "name": "Fictional CAPA document citation",
                "source_type": "other", "problem_statement": "Synthetic citation validation.",
                "owner_user_id": ids["pmc-user-a"],
            }), 201)
            link = checked(post(author, f"{WEB}/api/identity/capas/{capa['id']}/document-links", {
                "expected_version": capa["row_version"],
                "document_id": document["id"], "document_revision_id": revision["id"],
            }), 201)
            if link["status"] != "active" or link["file_sha256"] != hashlib.sha256(pdf).hexdigest():
                raise AssertionError("CAPA document snapshot missing released PDF hash")
            listed = checked(author.get(f"{WEB}/api/identity/capas/{capa['id']}/document-links"))
            if len(listed) != 1 or listed[0]["id"] != link["id"]:
                raise AssertionError("CAPA link list missed active citation")
            if owner.get(f"{API}/capas/{capa['id']}/document-links").status_code not in {403, 404}:
                raise AssertionError("tenant owner received implicit CAPA document authority")
            if post(author, f"{API}/capas/{capa['id']}/document-links", {
                "expected_version": capa["row_version"],
                "document_id": document["id"], "document_revision_id": revision["id"],
            }).status_code != 409:
                raise AssertionError("stale CAPA document version accepted")
            phase = "reasoned unlink and retained audit"
            removed = checked(post(author, f"{API}/capas/{capa['id']}/document-links/{link['id']}/remove", {
                "expected_version": link["capa_row_version"],
                "expected_link_version": link["row_version"],
                "reason": "Synthetic citation replaced for local validation.",
            }))
            if removed["status"] != "removed" or removed["snapshot_revision"] != "1.0":
                raise AssertionError("CAPA document unlink lost historical revision")
            events = checked(owner.get(f"{API}/audit/events?limit=100"))["items"]
            actions = {row["action"] for row in events if row["resource_id"] == link["id"]}
            if actions != {"capa.document_linked", "capa.document_unlinked"}:
                raise AssertionError("CAPA document link audit is incomplete")
        finally:
            if document is not None:
                try:
                    rows = checked(author.get(f"{API}/documents", params={
                        "unit_id": document["unit_id"], "search": document["code"],
                    }))
                    current = next(row for row in rows if row["id"] == document["id"])
                    cleanup_failed |= post(reviewer, f"{API}/documents/{document['id']}/obsolete", {
                        "expected_version": current["row_version"],
                    }).status_code != 200
                except Exception:  # noqa: BLE001 -- continue cleanup without exposing credentials
                    cleanup_failed = True
            for grant_id in reversed(grants):
                try:
                    cleanup_failed |= post(
                        owner, f"{API}/qms-access/grants/{grant_id}/revoke", {}
                    ).status_code != 200
                except Exception:  # noqa: BLE001 -- finish remaining grants
                    cleanup_failed = True
            for client in clients:
                if "pm_csrf" in client.cookies:
                    try:
                        cleanup_failed |= client.post(
                            f"{API}/auth/logout", headers=csrf(client)
                        ).status_code != 204
                    except Exception:  # noqa: BLE001 -- finish closing sessions
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError("CAPA document E2E cleanup could not be verified")
    print("OIDC, scanned PDF, CAPA document link, proxy, audit, cleanup: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- redact credentials and auth URLs
        raise SystemExit(f"CAPA document E2E failed during {phase}: {type(error).__name__}") from None
