#!/usr/bin/env python3
"""Offline, fail-closed reconciliation of a stale local agent task lease.

Input is a trusted operator-provided JSON snapshot of GitHub branches/PRs.
No network requests, lease deletion, auto-reclaim or deployment.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def decide(lease: dict, snapshot: dict, *, now: int) -> dict[str, str]:
    """Return an explicit, non-mutating decision and reason."""
    if not isinstance(lease, dict) or not isinstance(snapshot, dict):
        raise ValueError("lease and snapshot must be JSON objects")
    task = lease.get("task")
    if not isinstance(task, str) or not SAFE.fullmatch(task):
        raise ValueError("unsafe task identifier")
    if not isinstance(lease.get("owner"), str) or not SAFE.fullmatch(lease["owner"]):
        raise ValueError("unsafe owner identifier")
    expiry = lease.get("expires_at")
    if type(expiry) is not int or expiry < 0:
        raise ValueError("invalid lease expiration")
    if now < expiry:
        return {"decision": "blocked", "reason": "lease-active"}

    # The snapshot must be from an operator-verified source and be explicitly
    # associated with the same task and pinned 40-character commit SHA.
    if snapshot.get("task") != task:
        return {"decision": "blocked", "reason": "snapshot-task-mismatch"}
    sha = snapshot.get("head_sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        return {"decision": "blocked", "reason": "unverified-head"}
    if snapshot.get("source_verified") is not True:
        return {"decision": "blocked", "reason": "snapshot-not-verified"}
    if snapshot.get("worktree_present") is not False:
        return {"decision": "blocked", "reason": "worktree-needs-review"}
    prs = snapshot.get("open_prs")
    if not isinstance(prs, list) or any(not isinstance(pr, dict) for pr in prs):
        return {"decision": "blocked", "reason": "invalid-pr-snapshot"}
    if any(pr.get("task") == task for pr in prs):
        return {"decision": "blocked", "reason": "existing-pr-needs-review"}
    if snapshot.get("branch_exists") is not False:
        return {"decision": "blocked", "reason": "branch-needs-review"}
    return {"decision": "review-required", "reason": "no-artifacts-found-do-not-auto-reclaim"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    lease = json.loads(args.lease.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    print(json.dumps(decide(lease, snapshot, now=__import__("time").time_ns() // 1_000_000_000), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"reconciliation error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
