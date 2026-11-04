"""Exercise the local document workflow through OIDC, API, AV and S3 storage."""

from __future__ import annotations

import hashlib
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
UNIT_CODE = "DEV-ACCESS-UI"
PROCESS_CODE = "DEV-PROC-01"
CAPABILITIES = {
    "author": ("documents.author", "documents.read", "processes.read"),
    "reviewer": (
        "documents.read",
        "documents.review",
        "documents.approve",
        "documents.release",
        "documents.obsolete",
    ),
}
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
    response = client.post(form.action, data={"username": username, "password": password})
    if not response.is_success or client.get(f"{API}/auth/me").status_code != 200:
        raise AssertionError("local OIDC login failed")


def select_tenant(client: httpx.Client, slug: str) -> str:
    tenants = client.get(f"{API}/auth/tenants").json()
    tenant_id = next((tenant["id"] for tenant in tenants if tenant["slug"] == slug), None)
    if tenant_id is None:
        raise AssertionError("development tenant unavailable")
    response = client.post(
        f"{API}/auth/tenant", json={"tenant_id": tenant_id}, headers=csrf(client)
    )
    if response.status_code != 200:
        raise AssertionError("could not select the development tenant")
    return tenant_id


def post_json(client: httpx.Client, url: str, body: dict[str, object]) -> httpx.Response:
    return client.post(
        url,
        json=body,
        headers={**csrf(client), "Content-Type": "application/json"},
    )


def main() -> None:
    global phase
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("document E2E requires local development environment")

    document_id: str | None = None
    created_grants: list[str] = []
    with ExitStack() as stack:
        owner = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        author = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        reviewer = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        clients = (owner, author, reviewer)
        try:
            phase = "OIDC login"
            login(owner, "pmc-local-owner", str(env["KEYCLOAK_OWNER_PASSWORD"]))
            login(author, "pmc-user-a", str(env["KEYCLOAK_USER_A_PASSWORD"]))
            login(reviewer, "pmc-multi-user", str(env["KEYCLOAK_MULTI_USER_PASSWORD"]))
            select_tenant(owner, "tenant-a")
            select_tenant(author, "tenant-a")
            select_tenant(reviewer, "tenant-a")

            phase = "read development members and unit"
            members = owner.get(f"{API}/organization/members?limit=100").json()
            author_id = next(
                (
                    member["id"]
                    for member in members
                    if member["display_name"].startswith("pmc-user-a")
                ),
                None,
            )
            reviewer_id = next(
                (
                    member["id"]
                    for member in members
                    if member["display_name"].startswith("pmc-multi-user")
                ),
                None,
            )
            if not author_id or not reviewer_id:
                raise AssertionError("development author or reviewer membership unavailable")
            filtered_members = owner.get(
                f"{API}/organization/members?limit=100&search=pmc-user-a"
            ).json()
            if not any(member["id"] == author_id for member in filtered_members):
                raise AssertionError("tenant member search did not return its match")
            units = owner.get(f"{API}/organization/units?limit=100").json()
            unit = next(
                (row for row in units if row["code"] == UNIT_CODE and row["status"] == "active"),
                None,
            )
            if unit is None:
                raise AssertionError("development QMS unit unavailable")
            unit_id = unit["id"]

            grants = owner.get(f"{API}/qms-access/grants").json()
            phase = "grant temporary scoped capabilities"
            existing = {
                (grant["user_id"], grant["unit_id"], grant["capability"])
                for grant in grants
                if grant["status"] == "active"
            }
            for target_id, role in ((author_id, "author"), (reviewer_id, "reviewer")):
                for capability in CAPABILITIES[role]:
                    if (target_id, unit_id, capability) in existing:
                        continue
                    response = post_json(
                        owner,
                        f"{API}/qms-access/grants",
                        {
                            "user_id": target_id,
                            "unit_id": unit_id,
                            "capability": capability,
                        },
                    )
                    if response.status_code != 201:
                        raise AssertionError("could not grant a temporary QMS responsibility")
                    created_grants.append(response.json()["id"])

            phase = "read development process"
            process_references = author.get(
                f"{API}/documents/processes?unit_id={unit_id}&limit=100&search={PROCESS_CODE}"
            ).json()
            if not any(row["code"] == PROCESS_CODE for row in process_references):
                raise AssertionError("authorized active process search did not return its match")
            processes = author.get(f"{API}/processes?unit_id={unit_id}&limit=100").json()
            process = next(
                (
                    row
                    for row in processes
                    if row["code"] == PROCESS_CODE and row["status"] == "active"
                ),
                None,
            )
            if process is None:
                raise AssertionError("development QMS process unavailable")

            run_tag = uuid4().hex[:12]
            code = f"DEV-E2E-{run_tag}"
            phase = "create document and revision"
            created = post_json(
                author,
                f"{API}/documents",
                {
                    "unit_id": unit_id,
                    "process_id": process["id"],
                    "code": code,
                    "title": "Development document workflow verification",
                    "document_type": "procedure",
                    "owner_user_id": author_id,
                },
            )
            if created.status_code != 201:
                raise AssertionError("document creation failed")
            document = created.json()
            document_id = document["id"]
            revision_response = post_json(
                author,
                f"{API}/documents/{document_id}/revisions",
                {
                    "revision": "1.0",
                    "change_summary": "Local integration verification",
                    "revision_date": datetime.now(UTC).date().isoformat(),
                },
            )
            if revision_response.status_code != 201:
                raise AssertionError(
                    f"revision creation failed ({revision_response.status_code}: "
                    f"{revision_response.json().get('detail', 'no detail')})"
                )
            revision = revision_response.json()
            if not revision.get("prepared_by_display_name"):
                raise AssertionError("revision preparer display name was not returned")
            revision_id = revision["id"]

            pdf = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
            phase = "scan and store PDF"
            upload = author.put(
                f"{API}/documents/{document_id}/revisions/{revision_id}/file",
                content=pdf,
                headers={**csrf(author), "Content-Type": "application/pdf"},
            )
            if upload.status_code != 202 or upload.json().get("file_state") != "clean":
                raise AssertionError("local antivirus/storage upload did not return clean")

            submitted = post_json(
                reviewer,
                f"{API}/documents/{document_id}/revisions/{revision_id}/submit",
                {"expected_version": upload.json().get("row_version", 2)},
            )
            if submitted.status_code != 200:
                raise AssertionError(f"revision submission failed ({submitted.status_code})")
            phase = "independent approval"
            approved = post_json(
                reviewer,
                f"{API}/documents/{document_id}/revisions/{revision_id}/approve",
                {"expected_version": submitted.json()["row_version"]},
            )
            if approved.status_code != 200:
                raise AssertionError(f"independent approval failed ({approved.status_code})")
            decision = approved.json()
            if (
                not decision.get("review_date")
                or not decision.get("reviewed_by_display_name")
                or not decision.get("approved_by_display_name")
                or decision["prepared_by_user_id"] == decision["approved_by_user_id"]
            ):
                raise AssertionError("review decision details are incomplete or not independent")
            phase = "release revision"
            released = post_json(
                reviewer,
                f"{API}/documents/{document_id}/revisions/{revision_id}/release",
                {"expected_version": approved.json()["row_version"]},
            )
            if released.status_code != 200 or released.json()["status"] != "active":
                raise AssertionError(f"revision release failed ({released.status_code})")
            if "file_object_key" in released.json():
                raise AssertionError("private object key leaked through revision response")

            listing_url = f"{WEB}/api/identity/documents?unit_id={unit_id}&search={code}"
            phase = "read web proxy and revision history"
            visible = author.get(listing_url)
            if visible.status_code != 200 or not any(
                row["id"] == document_id for row in visible.json()
            ):
                raise AssertionError("document register is unavailable through the web proxy")
            history = author.get(f"{API}/documents/{document_id}/revisions")
            if history.status_code != 200 or not history.json():
                raise AssertionError("revision history could not be read")
            if any("file_object_key" in row for row in history.json()):
                raise AssertionError("private object key leaked through revision history")
            history_revision = next(row for row in history.json() if row["id"] == revision_id)
            if (
                not history_revision.get("prepared_by_display_name")
                or not history_revision.get("reviewed_by_display_name")
                or not history_revision.get("approved_by_display_name")
                or not history_revision.get("review_date")
                or not history_revision.get("effective_date")
            ):
                raise AssertionError("revision history is missing decision details")

            downloaded = author.get(
                f"{WEB}/api/identity/documents/{document_id}/revisions/{revision_id}/file"
            )
            phase = "download private PDF through web proxy"
            if (
                downloaded.status_code != 200
                or downloaded.content != pdf
                or downloaded.headers.get("cache-control") != "private, no-store"
                or downloaded.headers.get("x-content-type-options") != "nosniff"
            ):
                raise AssertionError("web-proxied private download failed integrity/header checks")
            if hashlib.sha256(downloaded.content).hexdigest() != upload.json()["sha256"]:
                raise AssertionError("web-proxied download hash did not match the uploaded PDF")

            listed = next(row for row in visible.json() if row["id"] == document_id)
            phase = "obsolete development record and audit"
            obsolete = post_json(
                reviewer,
                f"{API}/documents/{document_id}/obsolete",
                {"expected_version": listed["row_version"]},
            )
            if obsolete.status_code != 200 or obsolete.json()["status"] != "obsolete":
                raise AssertionError("test document could not be safely obsoleted")
            print(
                "Document E2E PASS: OIDC, tenant-scoped grants, create/revise, real AV scan, "
                "private storage, independent review/approval/release, web proxy, integrity "
                "download and obsolete audit. Test record retained as obsolete: "
                f"{code} ({document_id})."
            )
        finally:
            cleanup_failed = False
            if document_id is not None:
                try:
                    if "pm_session" in reviewer.cookies and "pm_csrf" in reviewer.cookies:
                        rows = author.get(
                            f"{API}/documents?unit_id={unit_id}&limit=100&search={code}"
                        ).json()
                        row = next((item for item in rows if item["id"] == document_id), None)
                        if row and row["status"] != "obsolete":
                            response = post_json(
                                reviewer,
                                f"{API}/documents/{document_id}/obsolete",
                                {"expected_version": row["row_version"]},
                            )
                            cleanup_failed |= response.status_code != 200
                except Exception:  # noqa: BLE001 -- continue cleanup after an endpoint failure.
                    cleanup_failed = True
            for grant_id in created_grants:
                try:
                    response = owner.post(
                        f"{API}/qms-access/grants/{grant_id}/revoke",
                        headers=csrf(owner),
                    )
                    cleanup_failed |= not response.is_success
                except Exception:  # noqa: BLE001 -- continue cleanup after an endpoint failure.
                    cleanup_failed = True
            if created_grants:
                try:
                    remaining = owner.get(f"{API}/qms-access/grants").json()
                    status_by_id = {row["id"]: row["status"] for row in remaining}
                    cleanup_failed |= any(
                        status_by_id.get(grant_id) != "revoked" for grant_id in created_grants
                    )
                except Exception:  # noqa: BLE001 -- continue cleanup after an endpoint failure.
                    cleanup_failed = True
            for client in clients:
                if "pm_session" in client.cookies and "pm_csrf" in client.cookies:
                    try:
                        response = client.post(f"{API}/auth/logout", headers=csrf(client))
                        cleanup_failed |= response.status_code != 204
                    except Exception:  # noqa: BLE001 -- close the remaining local test sessions.
                        cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError("test cleanup could not be verified")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(
            f"Document E2E failed during {phase}: {error}. Credentials and tokens are redacted."
        ) from None
    except Exception:  # noqa: BLE001 -- keep diagnostics free of URLs, tokens and credentials.
        raise SystemExit(
            f"Document E2E failed during {phase}; inspect local services. "
            "Credentials and tokens are redacted."
        ) from None
