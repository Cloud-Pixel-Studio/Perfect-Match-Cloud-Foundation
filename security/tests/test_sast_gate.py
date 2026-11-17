"""Exercise actual CI/local SAST commands and fixture exit-code handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SASTGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("opengrep") is None:
            raise RuntimeError(
                "Install the pinned scanner before running SAST gate tests"
            )
        workflow = (ROOT / ".github/workflows/security.yml").read_text()
        match = re.search(
            r"(?m)^      - name: OpenGrep SAST\n        run: (.+)$", workflow
        )
        if not match:
            raise AssertionError("Expected the real executable CI SAST command")
        local = re.findall(
            r"(?m)^opengrep scan .+$", (ROOT / "scripts/checkpoint.sh").read_text()
        )
        if len(local) != 1:
            raise AssertionError("Expected one local checkpoint SAST command")
        cls.commands = {
            "ci": shlex.split(match.group(1)),
            "checkpoint": shlex.split(local[0]),
        }

    def _scan(self, command, source):
        self.assertEqual(command[:2], ["opengrep", "scan"])
        self.assertEqual(
            command[-1], ".", "Regression must exercise the real project scan"
        )
        with tempfile.TemporaryDirectory(prefix="pmqms-sast-gate-") as folder:
            target = Path(folder)
            (target / "case.py").write_text(source)
            report = target / "result.sarif"
            args = list(command)
            args[-1] = str(target)
            if "--sarif" not in args:
                args[-1:-1] = ["--sarif"]
            if "--output" in args:
                args[args.index("--output") + 1] = str(report)
            else:
                args[-1:-1] = ["--output", str(report)]
            result = subprocess.run(
                args, cwd=ROOT, capture_output=True, text=True, timeout=45
            )
            self.assertTrue(report.is_file(), result.stderr[-1200:])
            return result, json.loads(report.read_text())

    def test_real_commands_block_findings_and_preserve_evidence(self):
        for name, command in self.commands.items():
            with self.subTest(command=name):
                result, report = self._scan(command, "AUTHORIZATION_BYPASS = True\n")
                self.assertEqual(result.returncode, 1, result.stderr[-1200:])
                self.assertTrue(
                    any(
                        entry["ruleId"].endswith(
                            "pmc.python.authentication-bypass-flag"
                        )
                        for run in report["runs"]
                        for entry in run.get("results", [])
                    )
                )

    def test_real_commands_allow_clean_code(self):
        for name, command in self.commands.items():
            with self.subTest(command=name):
                result, report = self._scan(
                    command, "def allowed():\n    return True\n"
                )
                self.assertEqual(result.returncode, 0, result.stderr[-1200:])
                self.assertEqual(
                    [r for run in report["runs"] for r in run.get("results", [])], []
                )

    def test_real_commands_block_reported_parser_warnings(self):
        # Valid Python3.12 syntax unsupported by the pinned scanner. Safe security
        # anchors make the scanner's rule prefilter parse this synthetic file.
        source = (
            "from __future__ import annotations\n\n"
            "def _persist[T: QMSControlActivity | QMSControlEvidenceRequirement](value: T) -> T:\n"
            "    return value\n\n"
            'response.set_cookie("sample", "safe", secure=True)\n'
            "AUTHORIZATION_BYPASS = False\n"
        )
        for name, command in self.commands.items():
            with self.subTest(command=name):
                result, report = self._scan(command, source)
                self.assertEqual(result.returncode, 3, result.stderr[-1200:])
                self.assertTrue(
                    any(
                        note.get("level") == "warning"
                        for run in report["runs"]
                        for invocation in run.get("invocations", [])
                        for note in invocation.get("toolExecutionNotifications", [])
                    )
                )

    def _fixture_checker(self, positive_exit):
        with tempfile.TemporaryDirectory(prefix="pmqms-sast-fixture-exit-") as folder:
            scanner = Path(folder) / "opengrep"
            scanner.write_text(
                "#!/usr/bin/env bash\n"
                'case "${!#}" in\n'
                f"  *_positive.py) exit {positive_exit} ;;\n"
                "  *_negative.py) exit 0 ;;\n"
                "  *) exit 2 ;;\n"
                "esac\n"
            )
            scanner.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = folder + os.pathsep + env.get("PATH", "")
            return subprocess.run(
                ["bash", "security/opengrep/test-rules.sh"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

    def test_fixture_checker_rejects_scanner_errors_as_positive_results(self):
        for status in (2, 3):
            with self.subTest(scanner_exit=status):
                result = self._fixture_checker(status)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fixture_checker_accepts_expected_finding_exit(self):
        result = self._fixture_checker(1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
