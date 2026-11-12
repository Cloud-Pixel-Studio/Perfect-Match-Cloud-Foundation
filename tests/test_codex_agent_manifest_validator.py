"""Regression tests for project-scoped Codex agent manifest validation.

Run: python3 -m unittest discover -s tests -p 'test_codex_agent_manifest_validator.py'
Requires Python >=3.11. No external packages or live services.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "scripts" / "check-codex-agents.py"


class AgentManifestValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        (self.root / ".codex" / "agents").mkdir(parents=True)
        shutil.copy2(VALIDATOR, self.root / "scripts" / VALIDATOR.name)
        shutil.copy2(REPO / ".codex" / "config.toml", self.root / ".codex" / "config.toml")
        for source in (REPO / ".codex" / "agents").glob("*.toml"):
            shutil.copy2(source, self.root / ".codex" / "agents" / source.name)

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / VALIDATOR.name)],
            text=True, capture_output=True, check=False, timeout=20,
        )

    def test_valid_project_specialists(self) -> None:
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("specialists", result.stdout)

    def test_rejects_parent_permission_override(self) -> None:
        path = self.root / ".codex" / "agents" / "ux_accessibility_reviewer.toml"
        with path.open("a", encoding="utf-8") as file:
            file.write('\nsandbox_mode = "danger-full-access"\n')
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sandbox_mode cannot override", result.stderr)

    def test_rejects_missing_required_specialist(self) -> None:
        (self.root / ".codex" / "agents" / "backend_engineer.toml").unlink()
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required specialist: backend_engineer", result.stderr)

    def test_rejects_unbounded_concurrency(self) -> None:
        path = self.root / ".codex" / "config.toml"
        path.write_text('[agents]\nenabled = true\nmax_concurrent_threads_per_session = 100\n', encoding="utf-8")
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("concurrency limit", result.stderr)


if __name__ == "__main__":
    unittest.main()
