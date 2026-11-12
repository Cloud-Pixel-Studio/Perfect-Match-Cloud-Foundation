#!/usr/bin/env python3
"""Fail closed when the third-party security scan targets drift from Compose."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("seaweedfs", "keycloak", "clamav", "clamav-database-bootstrap")
PIN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:@-]*@sha256:[0-9a-f]{64}$")


def validate(compose: str, workflow: str) -> list[str]:
    errors = []
    for service in SERVICES:
        section = re.search(r"^  " + service + r":\s*\n(?P<body>(?:^    .*\n|^\s*\n)*)", compose, re.M)
        if not section:
            errors.append(f"{service}: service missing")
            continue
        match = re.search(r"^    image:\s*(\S+)\s*$", section.group("body"), re.M)
        if not match:
            errors.append(f"{service}: image missing")
            continue
        image = match.group(1)
        if not PIN.fullmatch(image):
            errors.append(f"{service}: image is not digest-pinned")
            continue
        # Require the expected output artifact and exact digest on the same
        # executable scanner line. A commented-out or renamed scan is invalid.
        scan_service = "clamav" if service == "clamav-database-bootstrap" else service
        expected_output = f"artifacts/trivy-{scan_service}-image.json"
        commands = [
            line.strip()
            for line in workflow.splitlines()
            if line.lstrip().startswith("trivy image ")
        ]
        if not any(
            re.search(r"(?:^|\\s)--output\\s+" + re.escape(expected_output) + r"(?:\\s|$)", line)
            and line.split()[-1] == image
            for line in commands
        ):
            errors.append(f"{service}: security scan does not target Compose digest")
    return errors


def main() -> int:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
    errors = validate(compose, workflow)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Third-party image digests match security scan targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
