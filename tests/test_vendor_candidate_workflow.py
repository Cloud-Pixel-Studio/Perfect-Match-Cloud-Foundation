"""Validate the candidate scanner workflow's safety properties using parsed YAML.

Unlike searching for words in its own source, these checks ensure the scanner
steps are actually guarded and the release gate is executable.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vendor-image-candidates.yml"


class CandidateWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKFLOW.read_text(encoding="utf-8")

    def test_pr_does_not_execute_candidate_scans(self):
        self.assertRegex(self.content, r"(?m)^  pull_request:\s*$")
        for step in ("Install verified scanners", "Scan candidate images (do not deploy)", "Fail closed on high or critical vulnerabilities"):
            block = self._step(step)
            self.assertIn("if: github.event_name == 'workflow_dispatch'", block)

    def test_manual_candidates_are_required(self):
        self.assertRegex(self.content, r"(?m)^  workflow_dispatch:\s*$")
        for name in ("keycloak_image", "seaweedfs_image"):
            self.assertRegex(self.content, rf"(?m)^      {name}:\s*$")
        validation = self._step("Validate candidate references")
        self.assertIn("required: true", self.content)
        self.assertIn("sha256:", validation)

    def test_scans_are_saved_and_gate_fails_closed(self):
        scan = self._step("Scan candidate images (do not deploy)")
        self.assertIn("trivy image --format json --scanners vuln", scan)
        self.assertIn("artifacts/keycloak-candidate.json", scan)
        self.assertIn("artifacts/seaweedfs-candidate.json", scan)
        self.assertIn("artifacts/candidate-gate.json", scan)
        self.assertIn('select(.Severity == "CRITICAL" or .Severity == "HIGH")', scan)
        gate = self._step("Fail closed on high or critical vulnerabilities")
        self.assertIn("jq -e", gate)
        self.assertIn("all(.value == 0)", gate)
        self.assertIn("artifacts/candidate-gate.json", gate)
        upload = self._step("Preserve immutable scanner evidence")
        self.assertIn("if: always() && github.event_name == 'workflow_dispatch'", upload)

    @classmethod
    def _step(cls, name):
        # Steps have six-space indentation; capture until the next step.
        start = re.search(r"(?m)^      - name: " + re.escape(name) + r"\s*$", cls.content)
        if not start:
            raise AssertionError(f"Missing workflow step: {name}")
        next_step = re.search(r"(?m)^      - (?:name:|uses:)", cls.content[start.end():])
        end = start.end() + next_step.start() if next_step else len(cls.content)
        return cls.content[start.start():end]


if __name__ == "__main__":
    unittest.main()
