#!/usr/bin/env python3
"""Validate project-scoped Codex agent manifests using Python's standard library."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".codex" / "agents"
REQUIRED = {
    "application_security_reviewer",
    "backend_engineer",
    "database_rls_reviewer",
    "frontend_engineer",
    "independent_reviewer",
    "platform_sre",
    "qa_automation_engineer",
    "qms_product_architect",
    "saas_commercial_architect",
}
DISALLOWED_SESSION_OVERRIDES = {
    "approval_policy",
    "sandbox_mode",
    "model_provider",
    "mcp_servers",
}
ERRORS: list[str] = []


def load(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
        if not isinstance(value, dict):
            raise ValueError("TOML document must be a table")
        return value
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        ERRORS.append(f"{path.relative_to(ROOT)}: {error}")
        return {}


def main() -> int:
    config = load(ROOT / ".codex" / "config.toml")
    settings = config.get("agents")
    if not isinstance(settings, dict) or settings.get("enabled") is not True:
        ERRORS.append("Project must explicitly enable agents in .codex/config.toml")
    elif settings.get("max_concurrent_threads_per_session") != 4:
        ERRORS.append("Project concurrency limit must be 4 to coordinate overlapping work")

    found: set[str] = set()
    for path in sorted(AGENT_DIR.glob("*.toml")):
        agent = load(path)
        name = agent.get("name")
        description = agent.get("description")
        instructions = agent.get("developer_instructions")
        if not isinstance(name, str) or name != path.stem:
            ERRORS.append(f"{path.relative_to(ROOT)}: name must match file stem")
            continue
        if name in found:
            ERRORS.append(f"{path.relative_to(ROOT)}: duplicate agent name {name}")
        found.add(name)
        if not isinstance(description, str) or not description.strip():
            ERRORS.append(f"{name}: missing agent description")
        if not isinstance(instructions, str) or len(instructions.strip()) < 120:
            ERRORS.append(f"{name}: instructions must define meaningful boundaries")
        for invalid in DISALLOWED_SESSION_OVERRIDES.intersection(agent):
            ERRORS.append(f"{name}: {invalid} cannot override parent session permissions")

    if not found:
        ERRORS.append("No project agents were found")
    for name in sorted(REQUIRED - found):
        ERRORS.append(f"Missing required specialist: {name}")

    if ERRORS:
        for error in ERRORS:
            print(f"agent validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Codex agent configuration valid: {len(found)} specialists, maximum 4 threads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
