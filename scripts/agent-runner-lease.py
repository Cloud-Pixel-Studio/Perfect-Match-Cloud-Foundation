#!/usr/bin/env python3
"""Local-only atomic lease for a disposable development runner.

This is NOT a worker, scheduler, GitHub API client or production lock service.
One local filesystem/host only. Python 3.11+. No third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def claim(root: Path, task: str, owner: str, ttl: int, now: int | None = None) -> bool:
    if not IDENTIFIER.fullmatch(task) or not IDENTIFIER.fullmatch(owner):
        raise ValueError("task and owner must be safe identifiers")
    if not 1 <= ttl <= 86400:
        raise ValueError("ttl must be between 1 and 86400 seconds")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = int(time.time()) if now is None else now
    target = root / f"{task}.json"
    record = {"task": task, "owner": owner, "expires_at": now + ttl}
    # O_EXCL is atomic on a local filesystem. An expired lease is deliberately
    # NOT reclaimed automatically: reconcile worktrees and PRs first.
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(record, output, sort_keys=True)
        output.write("\n")
    return True


def inspect(root: Path, task: str, now: int | None = None) -> dict[str, object] | None:
    if not IDENTIFIER.fullmatch(task):
        raise ValueError("unsafe task identifier")
    path = root / f"{task}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("task") != task:
        raise ValueError("invalid lease record")
    current = int(time.time()) if now is None else now
    return {**data, "expired": current >= int(data["expires_at"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("claim", "inspect"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--owner")
    parser.add_argument("--ttl", type=int, default=900)
    args = parser.parse_args()
    if args.action == "claim":
        if not args.owner:
            parser.error("--owner required for claim")
        accepted = claim(args.root, args.task, args.owner, args.ttl)
        print("claimed" if accepted else "already-claimed")
        return 0 if accepted else 2
    print(json.dumps(inspect(args.root, args.task), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"lease error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
