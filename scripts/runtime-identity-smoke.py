"""Exercise the disposable local OIDC runtime without printing credentials or tokens."""

from __future__ import annotations

from contextlib import ExitStack
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

API = "http://127.0.0.1:8000"


class LoginForm(HTMLParser):
    action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


def login(client: httpx.Client, username: str, password: str) -> None:
    page = client.get(f"{API}/auth/login")
    page.raise_for_status()
    form = LoginForm()
    form.feed(page.text)
    assert form.action is not None, "expected local identity login form"
    target = urlparse(form.action)
    if (target.scheme, target.netloc) != ("http", "127.0.0.1:8080"):
        raise RuntimeError("refusing credentials outside the local identity provider")
    # Browsers treat loopback as trustworthy; httpx does not send Secure cookies
    # over local HTTP. Adapt only the test client's Keycloak cookies, never app
    # configuration or production cookies. This is not a browser validation.
    for cookie in client.cookies.jar:
        if cookie.domain == "127.0.0.1" and cookie.path == "/realms/perfect-match/":
            cookie.secure = False
    response = client.post(
        form.action, data={"username": username, "password": password}
    )
    assert response.is_success, "local OIDC login failed"
    assert client.get(f"{API}/auth/me").status_code == 200


def csrf(client: httpx.Client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["pm_csrf"]}


def main() -> None:
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("local development only")
    with ExitStack() as stack:
        first = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        second = stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
        login(first, "pmc-user-a", str(env["KEYCLOAK_USER_A_PASSWORD"]))
        login(second, "pmc-user-b", str(env["KEYCLOAK_USER_B_PASSWORD"]))
        try:
            tenants_a = first.get(f"{API}/auth/tenants").json()
            tenants_b = second.get(f"{API}/auth/tenants").json()
            assert len(tenants_a) == len(tenants_b) == 1
            assert tenants_a[0]["id"] != tenants_b[0]["id"]
            selected = {"tenant_id": tenants_a[0]["id"]}
            assert first.post(f"{API}/auth/tenant", json=selected).status_code == 403
            assert (
                first.post(
                    f"{API}/auth/tenant", json=selected, headers=csrf(first)
                ).status_code
                == 200
            )
            assert (
                first.post(
                    f"{API}/auth/tenant",
                    json={"tenant_id": tenants_b[0]["id"]},
                    headers=csrf(first),
                ).status_code
                == 403
            )
            assert first.get(f"{API}/organization/units").status_code == 200
            assert first.get(f"{API}/workflows").status_code == 200
            assert first.get(f"{API}/qms-access/grants").status_code == 200
            # A valid tenant ID is deliberately not an organizational unit;
            # members without a document grant must be denied before any write.
            document_query = {"unit_id": tenants_a[0]["id"]}
            document_response = first.get(f"{API}/documents", params=document_query)
            assert document_response.status_code == 403, (
                f"document API denied: {document_response.status_code}"
            )
            assert (
                first.get(
                    "http://127.0.0.1:3000/api/identity/qms-access/grants"
                ).status_code
                == 200
            )
            proxy_document_response = first.get(
                "http://127.0.0.1:3000/api/identity/documents",
                params=document_query,
            )
            assert proxy_document_response.status_code == 403, (
                f"document proxy denied: {proxy_document_response.status_code}"
            )
            missing_unit = first.get(
                "http://127.0.0.1:3000/api/identity/organization/units/60000000-0000-4000-8000-000000000001"
            )
            assert missing_unit.status_code == 404
            assert missing_unit.json() == {"detail": "organization unit not found"}
            assert (
                first.post(
                    f"{API}/qms-access/grants",
                    json={
                        "user_id": tenants_a[0]["id"],
                        "unit_id": tenants_a[0]["id"],
                        "capability": "documents.approve",
                    },
                    headers=csrf(first),
                ).status_code
                == 403
            )
            assert (
                first.post(
                    f"{API}/workflows",
                    json={"code": "denied", "name": "Denied"},
                    headers=csrf(first),
                ).status_code
                == 403
            )
            # Exercise the same-origin web proxy used by the browser.
            assert (
                first.get("http://127.0.0.1:3000/api/identity/auth/me").status_code
                == 200
            )
        finally:
            for client in (first, second):
                if "pm_csrf" in client.cookies:
                    assert (
                        client.post(
                            f"{API}/auth/logout", headers=csrf(client)
                        ).status_code
                        == 204
                    )
                    assert client.get(f"{API}/auth/me").status_code == 401
    print(
        "OIDC login, tenant isolation, CSRF, member permissions, web proxy and logout: PASS"
    )


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(
            f"Identity smoke assertion failed: {error}. Credentials redacted."
        ) from None
    except Exception:  # noqa: BLE001 -- keep diagnostics free of URLs, tokens and credentials.
        raise SystemExit(
            "Identity smoke failed; inspect local services. Credentials redacted."
        ) from None
