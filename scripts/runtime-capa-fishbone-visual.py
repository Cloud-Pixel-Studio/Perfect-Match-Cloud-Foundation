"""Hold temporary synthetic CAPA grants for a local browser review, then revoke them."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import httpx
from dotenv import dotenv_values

helpers = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API = helpers["API"]
login, csrf, select_tenant, post = (helpers[name] for name in ("login", "csrf", "select_tenant", "post"))


def main() -> None:
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError("visual review requires local development")
    created: list[str] = []
    with httpx.Client(follow_redirects=True, timeout=30) as owner:
        login(owner, "pmc-local-owner", str(env["KEYCLOAK_OWNER_PASSWORD"]))
        select_tenant(owner)
        try:
            members = owner.get(f"{API}/organization/members?limit=100").json()
            user_id = next(row["id"] for row in members if row["display_name"].startswith("pmc-multi-user"))
            units = owner.get(f"{API}/organization/units?limit=100").json()
            unit_id = next(row["id"] for row in units if row["code"] == "DEV-ACCESS-UI")
            active = {
                (row["user_id"], row["unit_id"], row["capability"])
                for row in owner.get(f"{API}/qms-access/grants").json()
                if row["status"] == "active"
            }
            for capability in ("capa.read", "capa.manage"):
                if (user_id, unit_id, capability) in active:
                    continue
                response = post(owner, f"{API}/qms-access/grants", {
                    "user_id": user_id, "unit_id": unit_id, "capability": capability,
                })
                if response.status_code != 201:
                    raise RuntimeError("temporary visual responsibility could not be granted")
                created.append(response.json()["id"])
            print("Temporary visual access ready for pmc-multi-user in Tenant A.", flush=True)
            input("Press Enter after the browser review to revoke temporary access: ")
        finally:
            for grant_id in reversed(created):
                response = post(owner, f"{API}/qms-access/grants/{grant_id}/revoke", {})
                if response.status_code != 200:
                    raise RuntimeError("temporary visual responsibility could not be revoked")
            owner.post(f"{API}/auth/logout", headers=csrf(owner))
            print("Temporary visual access revoked and owner session closed.", flush=True)


if __name__ == "__main__":
    main()
