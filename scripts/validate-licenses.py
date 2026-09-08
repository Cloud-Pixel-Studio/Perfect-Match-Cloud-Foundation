#!/usr/bin/env python3
"""Validate generated dependency license inventories without fail-open paths."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


BLOCKED = re.compile(r"AGPL|AFFERO|SSPL|SERVER SIDE PUBLIC LICENSE", re.IGNORECASE)
UNKNOWN = re.compile(r"UNKNOWN|UNRESOLVED|NOASSERTION", re.IGNORECASE)


def inventory_entries(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("licenses", "packages", "dependencies"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        if payload:
            return list(payload.values())
    return []


def load_inventory(path: Path) -> list[object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty license inventory: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed license inventory: {path}") from exc
    entries = inventory_entries(payload)
    if not entries:
        raise ValueError(f"license inventory has no entries: {path}")
    return entries


def validate(path: Path) -> int:
    entries = load_inventory(path)
    blocked: list[str] = []
    unknown: list[str] = []
    for entry in entries:
        text = json.dumps(entry, ensure_ascii=True, sort_keys=True)
        if BLOCKED.search(text):
            blocked.append(text)
        if UNKNOWN.search(text):
            unknown.append(text)
    if blocked:
        raise ValueError(f"blocked license detected in {path}")
    if unknown:
        raise ValueError(f"unknown or unresolved license detected in {path}")
    return len(entries)


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 5) or (len(argv) == 5 and argv[3] != "--summary-file"):
        print("usage: validate-licenses.py PYTHON_JSON NODE_JSON", file=sys.stderr)
        return 2
    try:
        python_count = validate(Path(argv[1]))
        node_count = validate(Path(argv[2]))
    except (OSError, ValueError) as exc:
        print(f"License validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"LICENSE_PYTHON_COUNT={python_count}")
    print(f"LICENSE_NODE_COUNT={node_count}")
    if len(argv) == 5:
        Path(argv[4]).write_text(
            json.dumps(
                {
                    "python_entries": python_count,
                    "node_entries": node_count,
                    "agpl": 0,
                    "sspl": 0,
                    "unknown": 0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print("Dependency license policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
