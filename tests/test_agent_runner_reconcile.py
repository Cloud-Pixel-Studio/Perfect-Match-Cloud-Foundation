"""Offline reconciliation decisions never delete or reclaim leases."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent-runner-reconcile.py"
SPEC = importlib.util.spec_from_file_location("agent_runner_reconcile", SCRIPT)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)
SHA = "a" * 40


class ReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lease = {"task": "issue-18", "owner": "worker-1", "expires_at": 100}
        self.snapshot = {
            "task": "issue-18", "head_sha": SHA, "source_verified": True,
            "worktree_present": False, "branch_exists": False, "open_prs": [],
        }

    def test_active_lease_blocks(self) -> None:
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=99)["reason"], "lease-active")

    def test_expired_without_artifacts_requires_review(self) -> None:
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=100)["decision"], "review-required")

    def test_existing_pr_blocks(self) -> None:
        self.snapshot["open_prs"] = [{"task": "issue-18", "number": 22}]
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "existing-pr-needs-review")

    def test_existing_branch_blocks(self) -> None:
        self.snapshot["branch_exists"] = True
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "branch-needs-review")

    def test_unverified_snapshot_blocks(self) -> None:
        self.snapshot["source_verified"] = False
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "snapshot-not-verified")

    def test_wrong_task_blocks(self) -> None:
        self.snapshot["task"] = "issue-19"
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "snapshot-task-mismatch")

    def test_invalid_sha_blocks(self) -> None:
        self.snapshot["head_sha"] = "abc"
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "unverified-head")

    def test_worktree_present_blocks(self) -> None:
        self.snapshot["worktree_present"] = True
        self.assertEqual(reconcile.decide(self.lease, self.snapshot, now=101)["reason"], "worktree-needs-review")


if __name__ == "__main__":
    unittest.main()
