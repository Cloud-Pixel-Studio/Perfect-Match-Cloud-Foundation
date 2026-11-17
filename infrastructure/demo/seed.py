"""Populate only the explicitly authorized, HTTPS-protected synthetic VM demo.

Reuses the additive sandbox loader, its ordinary QMS APIs and independent
actors. No SQL, permission bypass, automatic approvals, resets or deletions.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import stat
from contextlib import ExitStack
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from dotenv import dotenv_values

ORIGIN = "https://demo.3-238-70-198.sslip.io"
API = ORIGIN + "/api/identity"
COMPANIES = (
    (
        "tenant-a",
        (
            ("pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
            ("pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
            ("pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
        ),
    ),
    (
        "tenant-b",
        (
            ("pmc-company-b-owner", "KEYCLOAK_B_OWNER_PASSWORD"),
            ("pmc-user-b", "KEYCLOAK_USER_B_PASSWORD"),
            ("pmc-company-b-reviewer", "KEYCLOAK_B_REVIEWER_PASSWORD"),
        ),
    ),
)


class DemoError(Exception):
    """Constant safe messages; never print authentication material or bodies."""


class Form(HTMLParser):
    action: str | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.netloc == urlsplit(ORIGIN).netloc
        and parts.username is None
        and parts.password is None
    )


def check_request(request: httpx.Request) -> None:
    if not allowed(str(request.url)):
        raise DemoError("refusing request outside the authorized HTTPS demo")


def navigate(client: httpx.Client, response: httpx.Response) -> httpx.Response:
    for _ in range(12):
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        target = urljoin(str(response.url), response.headers.get("location", ""))
        if not allowed(target):
            raise DemoError("refusing redirect outside the authorized HTTPS demo")
        response = client.get(target)
    raise DemoError("demo redirect limit exceeded")


def login(client: httpx.Client, username: str, password: str) -> None:
    response = navigate(client, client.get(API + "/auth/login"))
    if response.status_code != 200:
        raise DemoError("demo login page unavailable")
    form = Form()
    form.feed(response.text)
    action = urljoin(str(response.url), form.action or "")
    if (
        not form.action
        or not allowed(action)
        or not urlsplit(action).path.startswith("/realms/perfect-match/login-actions/")
    ):
        raise DemoError("refusing credentials outside the approved identity form")
    response = navigate(
        client, client.post(action, data={"username": username, "password": password})
    )
    if response.status_code != 200 or client.get(API + "/auth/me").status_code != 200:
        raise DemoError("demo OIDC login failed")


def csrf(client: httpx.Client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["pm_csrf"], "Origin": ORIGIN}


def load_sandbox():
    source = Path(__file__).resolve().parents[2] / "scripts/seed-demo-sandbox.py"
    spec = importlib.util.spec_from_file_location("private_vm_sandbox", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.API = API
    module.IDENTITY["csrf"] = csrf
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    config = args.env_file.expanduser()
    if config.is_symlink() or stat.S_IMODE(config.stat().st_mode) != 0o600:
        raise DemoError("demo configuration must be a private regular file")
    env = dotenv_values(config)
    if env.get("DEMO_ORIGIN") != ORIGIN or env.get("POSTGRES_DB") != "pmqms_demo":
        raise DemoError("configuration is not the approved isolated demo")
    sandbox = load_sandbox()
    result = {"origin": ORIGIN, "synthetic": True, "companies": []}
    for slug, actors in COMPANIES:
        with ExitStack() as stack:
            clients = []
            try:
                for username, key in actors:
                    client = stack.enter_context(
                        httpx.Client(
                            timeout=120,
                            follow_redirects=False,
                            event_hooks={"request": [check_request]},
                        )
                    )
                    clients.append(client)
                    login(client, username, env[key])
                    response = client.get(API + "/auth/tenants")
                    if response.status_code != 200:
                        raise DemoError("demo company list unavailable")
                    company = next(
                        (x for x in response.json() if x["slug"] == slug), None
                    )
                    if company is None:
                        raise DemoError("demo actor lacks the expected company")
                    response = client.post(
                        API + "/auth/tenant",
                        json={"tenant_id": company["id"]},
                        headers=csrf(client),
                    )
                    if response.status_code != 200:
                        raise DemoError("demo company selection failed")
                area = sandbox.Sandbox(*clients)
                seeded = area.run() if args.apply else {}
                result["companies"].append(
                    {"slug": slug, "seed": seeded, "inventory": area.inventory()}
                )
            finally:
                for client in clients:
                    if "pm_csrf" in client.cookies:
                        try:
                            client.post(API + "/auth/logout", headers=csrf(client))
                        except httpx.HTTPError:
                            pass
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- redact URLs, tokens and authentication bodies
        message = str(error) if isinstance(error, DemoError) else type(error).__name__
        raise SystemExit("Private demo stopped: " + message) from None
