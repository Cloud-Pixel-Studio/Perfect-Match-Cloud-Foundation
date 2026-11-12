"""Regression tests for the standalone Trivy CVE inventory."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trivy_cve_inventory.py"
spec = importlib.util.spec_from_file_location("trivy_cve_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def test_empty_results(self):
        self.assertEqual(module.inventory({"Results": []}, "image@sha256:" + "a" * 64), [])

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
        report = {"Results": [{"Vulnerabilities": [
            {"VulnerabilityID": "CVE-3", "PkgName": "pkg", "InstalledVersion": "1", "Severity": "CRITICAL"},
        ]}]}
        self.assertEqual(module.inventory(report, "digest")[0]["fixed_version"], "")

    def test_malformed_report_fails_closed(self):
        for report in ({}, {"Results": None}, {"Results": [{} , "bad"]}, {"Results": [{"Vulnerabilities": "invalid"}]}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                module.inventory(report, "digest")

    def test_missing_severity_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Vulnerabilities": [{"VulnerabilityID": "CVE-1"}]}]}, "digest")

    def test_invalid_target_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Target": [], "Vulnerabilities": []}]}, "digest")

    def test_incomplete_high_fails_closed(self):
        with self.assertRaises(ValueError):
            module.inventory({"Results": [{"Vulnerabilities": [{"Severity": "HIGH"}]}]}, "digest")


if __name__ == "__main__":
    unittest.main()
