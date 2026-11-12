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
        for step in ("Scan Keycloak candidate with pinned Trivy action", "Scan candidate images (do not deploy)", "Fail closed on high or critical vulnerabilities"):
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
        keycloak = self._step("Scan Keycloak candidate with pinned Trivy action")
        self.assertIn("aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25", keycloak)
        self.assertIn("image-ref: ${{ inputs.keycloak_image }}", keycloak)
        self.assertIn("output: artifacts/keycloak-candidate.json", keycloak)
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

    def test_pr_candidate_scan_is_fail_closed_after_evidence_upload(self):
        scan = self._step("Scan resolved candidate digests and record gate on PR")
        upload = self._step("Upload PR candidate evidence")
        gate = self._step("Fail closed on PR candidate high or critical findings")
        self.assertIn("artifacts/pr-candidate-gate.json", scan)
        self.assertIn("if: always() && github.event_name == 'pull_request'", upload)
        self.assertIn("if: github.event_name == 'pull_request'", gate)
        self.assertIn("set -euo pipefail", gate)
        self.assertIn("artifacts/pr-candidate-gate.json", gate)
        self.assertIn(".high_or_critical.keycloak", gate)
        self.assertIn(".high_or_critical.seaweedfs", gate)
        self.assertLess(self.content.index("name: Upload PR candidate evidence"),
                        self.content.index("name: Fail closed on PR candidate high or critical findings"))

    def test_pr_workflow_regression_runs_before_expected_vulnerability_failure(self):
        # Known vendor CVEs must not suppress the workflow's own structural tests.
        regression = self._step("Validate candidate workflow structure on PR")
        gate = self._step("Fail closed on PR candidate high or critical findings")
        self.assertIn("python3 -m unittest discover", regression)
        self.assertIn("if: github.event_name == 'pull_request'", regression)
        self.assertIn("if: github.event_name == 'pull_request'", gate)
        self.assertLess(
            self.content.index("name: Validate candidate workflow structure on PR"),
            self.content.index("name: Fail closed on PR candidate high or critical findings"),
        )

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
