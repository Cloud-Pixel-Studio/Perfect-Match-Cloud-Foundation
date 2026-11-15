"""Synthetic local lease tests; no network, daemon or production resources."""
from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent-runner-lease.py"
SPEC = importlib.util.spec_from_file_location("agent_runner_lease", SCRIPT)
assert SPEC and SPEC.loader
lease = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lease)


class AgentRunnerLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "leases"

    def test_single_claim_and_owner(self) -> None:
        self.assertTrue(lease.claim(self.root, "issue-18", "worker-1", 120, now=100))
        self.assertFalse(lease.claim(self.root, "issue-18", "worker-2", 120, now=101))
        self.assertEqual(lease.inspect(self.root, "issue-18", now=101)["owner"], "worker-1")

    def test_expired_lease_requires_explicit_reconciliation(self) -> None:
        self.assertTrue(lease.claim(self.root, "task", "worker-1", 10, now=100))
        self.assertTrue(lease.inspect(self.root, "task", now=110)["expired"])
        self.assertFalse(lease.claim(self.root, "task", "worker-2", 10, now=111))

    def test_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            lease.claim(self.root, "../escape", "worker", 10)
        with self.assertRaises(ValueError):
            lease.inspect(self.root, "../../escape")

    def test_rejects_invalid_ttl(self) -> None:
        for ttl in (0, -1, 86401):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                lease.claim(self.root, "task", "worker", ttl)

    def test_concurrent_claims_only_one_wins(self) -> None:
        # Exercise actual competing claims against the same local path.
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda index: lease.claim(self.root, "shared-task", f"worker-{index}", 60, now=100),
                range(24),
            ))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(list(self.root.glob("shared-task.json"))), 1)

    def test_corrupt_lease_is_not_silently_reclaimed(self) -> None:
        self.root.mkdir(parents=True)
        (self.root / "task.json").write_text("not-json", encoding="utf-8")
        self.assertFalse(lease.claim(self.root, "task", "worker-2", 60, now=100))
        with self.assertRaises(ValueError):
            lease.inspect(self.root, "task")

    def test_missing_lease(self) -> None:
        self.assertIsNone(lease.inspect(self.root, "missing"))


if __name__ == "__main__":
    unittest.main()
