"""Regression tests for the standalone Trivy CVE inventory."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trivy_cve_inventory.py"
spec = importlib.util.spec_from_file_location("trivy_cve_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def test_empty_results_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "non-empty Results"):
            module.inventory({"Results": []}, "image@sha256:" + "a" * 64)

    def test_valid_results_with_no_vulnerabilities(self):
        self.assertEqual(module.inventory({"Results": [{"Target": "os", "Vulnerabilities": []}]}, "image@sha256:" + "a" * 64), [])

    def test_valid_high_and_critical_only(self):
        report = {"Results": [{"Target": "os", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-1", "PkgName": "lib", "InstalledVersion": "1", "FixedVersion": "2", "Severity": "HIGH"},
            {"VulnerabilityID": "CVE-2", "PkgName": "other", "InstalledVersion": "1", "Severity": "LOW"},
        ]}]}
        rows = module.inventory(report, "image@sha256:" + "a" * 64)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fixed_version"], "2")
        self.assertEqual(rows[0]["cve"], "CVE-1")

    def test_no_fix_reported(self):
        report = {"Results": [{"Target": "os", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-3", "PkgName": "pkg", "InstalledVersion": "1", "Severity": "CRITICAL"},
        ]}]}
        self.assertEqual(module.inventory(report, "digest")[0]["fixed_version"], "")

    def test_malformed_report_fails_closed(self):
        for report in ({}, {"Results": None}, {"Results": [{"Target": "os"}, "bad"]}, {"Results": [{"Target": "os", "Vulnerabilities": "invalid"}]}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                module.inventory(report, "digest")

    def test_missing_severity_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Target": "os", "Vulnerabilities": [{"VulnerabilityID": "CVE-1"}]}]}, "digest")

    def test_non_string_severity_fails_closed(self):
        for severity in ([], {}, 5, None):
            with self.subTest(severity=severity), self.assertRaises(ValueError):
                module.inventory({"Results": [{"Target": "os", "Vulnerabilities": [{"Severity": severity}]}]}, "digest")

    def test_missing_or_blank_target_fails_closed(self):
        for target in (None, "", "  ", [], {}):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "non-empty"):
                module.inventory({"Results": [{"Target": target, "Vulnerabilities": []}]}, "digest")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            module.inventory({"Results": [{"Vulnerabilities": []}]}, "digest")

    def test_invalid_target_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Target": [], "Vulnerabilities": []}]}, "digest")

    def test_incomplete_high_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Target": "os", "Vulnerabilities": [{"Severity": "HIGH"}]}]}, "digest")


    def test_cli_removes_stale_output_on_invalid_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "invalid.json"
            report.write_text('{"Results": []}', encoding="utf-8")
            output = root / "inventory.json"
            output.write_text('{"stale": true}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", "image@sha256:" + "a" * 64, str(report), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_cli_writes_complete_valid_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "valid.json"
            report.write_text(json.dumps({"Results": [{"Target": "os", "Vulnerabilities": []}]}), encoding="utf-8")
            output = root / "inventory.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", "image@sha256:" + "a" * 64, str(report), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["high_or_critical_count"], 0)
            self.assertFalse(list(root.glob(".trivy-inventory-*.tmp")))


if __name__ == "__main__":
    unittest.main()
