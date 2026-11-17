"""Check workflow guards and execute its actual jq report validators."""
import json
from pathlib import Path
import re
import shutil
import subprocess
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
        self.assertIn(".high_or_critical.keycloak == 0", gate)
        self.assertIn(".high_or_critical.seaweedfs == 0", gate)
        self.assertIn("artifacts/candidate-gate.json", gate)
        upload = self._step("Preserve immutable scanner evidence")
        self.assertIn("if: always() && github.event_name == 'workflow_dispatch'", upload)

    def test_pr_scans_only_unique_expected_repository_digests(self):
        scan = self._step("Scan resolved candidate digests and record gate on PR")
        self.assertIn('select(startswith("quay.io/keycloak/keycloak@sha256:"))', scan)
        self.assertIn('select(startswith("chrislusf/seaweedfs@sha256:"))', scan)
        self.assertEqual(scan.count('if length == 1 then .[0] else error('), 2)
        self.assertNotIn("jq -r '.[0]'", scan)
        self.assertIn('trivy image --format json --scanners vuln', scan)

    def test_pr_reports_reject_malformed_vulnerability_sections(self):
        scan = self._step("Scan resolved candidate digests and record gate on PR")
        self.assertIn('(.Results | type == "array")', scan)
        self.assertIn('all(.Results[];', scan)
        self.assertIn('artifacts/keycloak-pr-candidate.json artifacts/seaweedfs-pr-candidate.json', scan)

    def test_actual_report_filters_accept_clean_results_and_known_severities(self):
        rows = [{}, {"Vulnerabilities": None}, {"Vulnerabilities": []}]
        rows.extend(
            {"Vulnerabilities": [{"Severity": severity}]}
            for severity in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")
        )
        for step in self._report_steps():
            for row in rows:
                with self.subTest(step=step, row=row):
                    self.assertEqual(self._validate_report(step, {"Results": [row]}).returncode, 0)

    def test_actual_report_filters_reject_malformed_vulnerability_sections(self):
        reports = [{"Results": [{"Vulnerabilities": value}]} for value in (False, True, 0, "", {})]
        reports.extend([{}, None, [], {"Results": []}, {"Results": False}, {"Results": [False]}])
        for step in self._report_steps():
            for report in reports:
                with self.subTest(step=step, report=report):
                    self.assertNotEqual(self._validate_report(step, report).returncode, 0)

    def test_actual_report_filters_reject_unrecognized_or_missing_severity(self):
        entries = [None, False, "HIGH", {}, {"Severity": None}, {"Severity": False},
                   {"Severity": 0}, {"Severity": ""}, {"Severity": "high"}, {"Severity": "OTHER"}]
        for step in self._report_steps():
            for entry in entries:
                with self.subTest(step=step, entry=entry):
                    report = {"Results": [{"Vulnerabilities": [entry]}]}
                    self.assertNotEqual(self._validate_report(step, report).returncode, 0)

    def test_actual_final_gates_require_both_numeric_zero_counts(self):
        clean = {"high_or_critical": {"keycloak": 0, "seaweedfs": 0}}
        rejected = [{}, None, {"high_or_critical": {}},
                    {"high_or_critical": {"keycloak": 0}},
                    {"high_or_critical": {"keycloak": False, "seaweedfs": 0}},
                    {"high_or_critical": {"keycloak": "0", "seaweedfs": 0}},
                    {"high_or_critical": {"keycloak": 1, "seaweedfs": 0}},
                    {"high_or_critical": {"keycloak": 0, "seaweedfs": 1}}]
        for step in ("Fail closed on PR candidate high or critical findings",
                     "Fail closed on high or critical vulnerabilities"):
            programs = re.findall(r"jq -e\s+'([^']+)'", self._step(step))
            self.assertEqual(len(programs), 1)
            self.assertEqual(self._execute_program(programs[0], clean).returncode, 0)
            for report in rejected:
                with self.subTest(step=step, report=report):
                    self.assertNotEqual(self._execute_program(programs[0], report).returncode, 0)

    @staticmethod
    def _report_steps():
        return ("Scan resolved candidate digests and record gate on PR",
                "Scan candidate images (do not deploy)")

    def _validate_report(self, step, report):
        programs = re.findall(r"jq -e\s+'([^']+)'\s+\"\$report\"", self._step(step))
        self.assertEqual(len(programs), 1, "Expected exactly one executable report-schema filter")
        return self._execute_program(programs[0], report)

    def _execute_program(self, program, report):
        jq = shutil.which("jq")
        self.assertIsNotNone(jq, "jq is required to test the candidate scanner's real filters")
        return subprocess.run([jq, "-e", program], input=json.dumps(report),
                              text=True, capture_output=True, check=False)

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
        self.assertIn("(.high_or_critical.keycloak | type)", gate)
        self.assertIn(".high_or_critical.keycloak == 0", gate)
        self.assertIn(".high_or_critical.seaweedfs == 0", gate)
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
