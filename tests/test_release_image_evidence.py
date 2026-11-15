# ruff: noqa: S603, S607
# Subprocesses below use the interpreter/shell and owned synthetic fixtures only.
"""Consistency and fail-closed tests; synthetic reports do not remediate a CVE."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "release_image_evidence", SCRIPTS / "release_image_evidence.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40
NOW = datetime.now(timezone.utc)
START = NOW - timedelta(minutes=1)


def fixture():
    inspected, scans = [], []
    for index, role in enumerate(sorted(module.ROLES), 1):
        image_id = "sha256:" + format(index, "064x")
        if role in {"api", "web"}:
            reference = f"pmcloud-{role}:{SHA}"
        elif role == "postgres":
            reference = "pmcloud-postgres:local"
        else:
            reference = module.REPOSITORIES[role] + ":test@sha256:" + format(index + 20, "064x")
        remote = "@" in reference
        field = "RepoDigests" if remote else "RepoTags"
        names = [module.normalized_digest(reference) if remote else reference]
        inspected.append({"Id": image_id, "Os": "linux", "Architecture": "amd64", field: names})
        report = {
            "SchemaVersion": 2,
            "ArtifactName": reference,
            "ArtifactType": "container_image",
            "CreatedAt": (NOW - timedelta(seconds=1)).isoformat(),
            "Metadata": {
                "ImageID": image_id,
                field: names,
                "ImageConfig": {"os": "linux", "architecture": "amd64"},
            },
            "Results": [{"Target": role, "Class": "os-pkgs"}],
        }
        scans.append(
            {
                "role": role,
                "reference": reference,
                "path": f"/{role}.json",
                "sha256": "b" * 64,
                "report": report,
            }
        )
    return inspected, scans


def build(images, scans):
    return module.build_evidence(images, scans, SHA, "12345", START, NOW)


class EvidenceTests(unittest.TestCase):
    def test_valid_six_images_and_vendor_without_tags(self):
        images, scans = fixture()
        result = build(images, scans)
        self.assertTrue(result["integrity_verified"])
        self.assertFalse(result["production_authorized"])
        self.assertEqual(len(result["images"]), 6)
        self.assertEqual(result["high_or_critical_count"], 0)
        self.assertTrue(
            all(row["identity_kind"] == "docker_configuration_digest" for row in result["images"])
        )

    def test_high_and_critical_are_counted_without_ignores(self):
        images, scans = fixture()
        scans[0]["report"]["Results"][0]["Vulnerabilities"] = [
            {
                "VulnerabilityID": "CVE-SYNTHETIC-1",
                "PkgName": "fixture",
                "InstalledVersion": "1",
                "FixedVersion": "2",
                "Severity": "HIGH",
            },
            {
                "VulnerabilityID": "CVE-SYNTHETIC-2",
                "PkgName": "fixture",
                "InstalledVersion": "1",
                "Severity": "CRITICAL",
            },
        ]
        result = build(images, scans)
        self.assertEqual(result["high_or_critical_count"], 2)
        self.assertEqual(result["findings"][1]["fixed_version"], "")

    def test_missing_duplicate_or_unknown_roles_fail(self):
        for mode in ("missing", "duplicate", "unknown"):
            with self.subTest(mode=mode):
                images, scans = fixture()
                if mode == "missing":
                    scans.pop()
                else:
                    scans[-1]["role"] = scans[0]["role"] if mode == "duplicate" else "untrusted"
                with self.assertRaises(ValueError):
                    build(images, scans)

    def test_reused_report_fails(self):
        images, scans = fixture()
        scans[-1]["path"] = scans[0]["path"]
        with self.assertRaises(ValueError):
            build(images, scans)

    def test_image_inspection_must_be_complete_and_distinct(self):
        for mode in ("missing", "duplicate", "bad_id", "platform"):
            with self.subTest(mode=mode):
                images, scans = fixture()
                if mode == "missing":
                    images.pop()
                elif mode == "duplicate":
                    images[-1]["Id"] = images[0]["Id"]
                elif mode == "bad_id":
                    images[0]["Id"] = "not-an-image-id"
                else:
                    images[0]["Os"] = "windows"
                with self.assertRaises(ValueError):
                    build(images, scans)

    def test_wrong_artifact_and_schema_fail(self):
        for field, value in (
            ("ArtifactName", "other-image:latest"),
            ("ArtifactType", "filesystem"),
            ("SchemaVersion", 1),
        ):
            with self.subTest(field=field):
                images, scans = fixture()
                scans[0]["report"][field] = value
                with self.assertRaises(ValueError):
                    build(images, scans)

    def test_wrong_or_missing_image_id_fails(self):
        for value in (None, "", "sha256:" + "f" * 64):
            images, scans = fixture()
            scans[0]["report"]["Metadata"]["ImageID"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build(images, scans)

    def test_wrong_platform_and_tag_fail(self):
        for mode in ("platform", "tag"):
            images, scans = fixture()
            if mode == "platform":
                scans[0]["report"]["Metadata"]["ImageConfig"]["architecture"] = "arm64"
            else:
                scans[0]["report"]["Metadata"]["RepoTags"] = ["pmcloud-api:older"]
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build(images, scans)

    def test_pinned_vendor_digest_is_not_configuration_id(self):
        images, scans = fixture()
        vendor = next(row for row in scans if row["role"] == "keycloak")
        vendor["report"]["Metadata"]["RepoDigests"] = [
            module.REPOSITORIES["keycloak"] + "@" + vendor["report"]["Metadata"]["ImageID"]
        ]
        with self.assertRaises(ValueError):
            build(images, scans)

    def test_cross_role_alias_cannot_leave_an_inspected_image_unused(self):
        images, scans = fixture()
        api = next(row for row in scans if row["role"] == "api")
        web = next(row for row in scans if row["role"] == "web")
        first = next(row for row in images if row["Id"] == api["report"]["Metadata"]["ImageID"])
        unused = next(row for row in images if row["Id"] == web["report"]["Metadata"]["ImageID"])
        first["RepoTags"].append(web["reference"])
        unused["RepoTags"] = ["unused:test"]
        web["report"]["Metadata"]["ImageID"] = first["Id"]
        with self.assertRaises(ValueError):
            build(images, scans)

    def test_old_application_reference_fails_even_with_matching_scan_metadata(self):
        images, scans = fixture()
        scans[0]["reference"] = "pmcloud-api:" + "c" * 40
        scans[0]["report"]["ArtifactName"] = scans[0]["reference"]
        with self.assertRaises(ValueError):
            build(images, scans)

    def test_stale_future_naive_and_invalid_report_times_fail(self):
        for value in (
            (START - timedelta(seconds=1)).isoformat(),
            (NOW + timedelta(minutes=1)).isoformat(),
            "2026-11-15T00:00:00",
            "invalid",
        ):
            images, scans = fixture()
            scans[0]["report"]["CreatedAt"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build(images, scans)

    def test_scan_time_not_build_time_controls_freshness(self):
        images, scans = fixture()
        scans[0]["report"]["Metadata"]["ImageConfig"]["created"] = "2020-01-01T00:00:00Z"
        self.assertTrue(build(images, scans)["integrity_verified"])

    def test_expired_scan_window_fails(self):
        images, scans = fixture()
        with self.assertRaises(ValueError):
            module.build_evidence(images, scans, SHA, "12345", NOW - timedelta(hours=2), NOW)

    def test_malformed_results_never_become_zero_findings(self):
        for results in (
            [],
            [{"Target": " ", "Class": "os-pkgs"}],
            [{"Target": "os", "Class": "os-pkgs", "Vulnerabilities": {}}],
            [
                {
                    "Target": "os",
                    "Class": "os-pkgs",
                    "Vulnerabilities": [{"Severity": "unrecognized"}],
                }
            ],
            [{"Target": "secret", "Class": "secret"}],
        ):
            images, scans = fixture()
            scans[-1]["report"]["Results"] = results
            with self.subTest(results=results), self.assertRaises(ValueError):
                build(images, scans)

    def test_secret_counts_are_recorded_without_values(self):
        images, scans = fixture()
        marker = "synthetic-sensitive-match"
        scans[0]["report"]["Results"][0]["Secrets"] = [{"Severity": "HIGH", "Match": marker}]
        result = build(images, scans)
        self.assertEqual(result["secret_high_or_critical_count"], 1)
        self.assertNotIn(marker, json.dumps(result))

    def test_malformed_secret_findings_fail(self):
        for value in ({}, "", [{"Severity": None}], [{"Severity": []}]):
            images, scans = fixture()
            scans[0]["report"]["Results"][0]["Secrets"] = value
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                build(images, scans)

    def cli_fixture(self, directory):
        images, scans = fixture()
        root = Path(directory)
        inspection = root / "images.json"
        inspection.write_text(json.dumps(images))
        start = root / "start.txt"
        start.write_text(START.isoformat())
        output = root / "evidence.json"
        command = [
            sys.executable,
            str(SCRIPTS / "release_image_evidence.py"),
            "--inspection",
            str(inspection),
            "--scan-started-at",
            str(start),
            "--source-sha",
            SHA,
            "--run-id",
            "12345",
            "--output",
            str(output),
        ]
        for row in scans:
            path = root / (row["role"] + ".json")
            path.write_text(json.dumps(row["report"]))
            command.extend(["--report", row["role"], row["reference"], str(path)])
        return command, output, scans

    def test_cli_validates_then_publishes_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(output.read_text())["integrity_verified"])
            self.assertEqual(list(Path(directory).glob(".release-images-*.tmp")), [])

    def test_cli_console_is_static_while_evidence_keeps_finding_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            path = Path(directory) / "api.json"
            report = json.loads(path.read_text())
            report["Results"][0]["Vulnerabilities"] = [
                {
                    "VulnerabilityID": "CVE-SYNTHETIC-LOG",
                    "PkgName": "synthetic-package",
                    "InstalledVersion": "1",
                    "Severity": "HIGH",
                }
            ]
            report["Results"][0]["Secrets"] = [
                {"Severity": "HIGH", "Match": "synthetic-private-match"}
            ]
            path.write_text(json.dumps(report))
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                "Bound 6 images; details are in release evidence; not production authorization\n",
            )
            self.assertEqual(result.stderr, "")
            payload = json.loads(output.read_text())
            self.assertEqual(payload["high_or_critical_count"], 1)
            self.assertEqual(payload["secret_high_or_critical_count"], 1)
            self.assertFalse(payload["production_authorized"])
            self.assertNotIn("synthetic-private-match", output.read_text())

    def test_cli_invalid_timestamp_does_not_echo_scanner_values(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            path = Path(directory) / "api.json"
            report = json.loads(path.read_text())
            report["CreatedAt"] = "synthetic-private-timestamp"
            path.write_text(json.dumps(report))
            output.write_text('{"stale_success":true}')
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Release image evidence failed closed; verify input reports locally.\n",
            )
            self.assertNotIn("synthetic-private-timestamp", result.stderr)
            self.assertFalse(output.exists())

    def test_cli_file_error_does_not_echo_input_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            command[command.index("--inspection") + 1] = str(
                Path(directory) / "private-runtime-input.json"
            )
            output.write_text('{"stale_success":true}')
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Release image evidence failed closed; verify input reports locally.\n",
            )
            self.assertNotIn("private-runtime-input", result.stderr)
            self.assertFalse(output.exists())

    def test_sixth_invalid_report_removes_stale_output(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, scans = self.cli_fixture(directory)
            output.write_text('{"stale_success":true}')
            (Path(directory) / (scans[-1]["role"] + ".json")).write_text('{"Results":[]}')
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).glob(".release-images-*.tmp")), [])

    def test_duplicate_keys_in_json_fail_and_invalidate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            output.write_text('{"stale_success":true}')
            (Path(directory) / "api.json").write_text('{"SchemaVersion":2,"SchemaVersion":2}')
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_output_cannot_overwrite_input_report(self):
        with tempfile.TemporaryDirectory() as directory:
            command, output, _ = self.cli_fixture(directory)
            source = Path(directory) / "api.json"
            before = source.read_bytes()
            command[command.index("--output") + 1] = str(source)
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(output.exists())


class ComposeCollectorTests(unittest.TestCase):
    def test_compose_vendor_plan_requires_pinned_expected_images(self):
        _, scans = fixture()
        services = {row["role"]: {"image": row["reference"]} for row in scans}
        self.assertEqual(
            set(module.compose_vendor_references({"services": services})),
            {"seaweedfs", "keycloak", "clamav"},
        )
        for value in (
            "latest",
            "other/image:tag@sha256:" + "a" * 64,
            "quay.io/keycloak/keycloak:$(bad)@sha256:" + "a" * 64,
        ):
            bad = copy.deepcopy(services)
            bad["keycloak"]["image"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.compose_vendor_references({"services": bad})

    def test_collector_uses_compose_pins_without_persisting_environment_values(self):
        import os

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images, scans = fixture()
            marker = "synthetic-do-not-persist-environment-value"
            services = {row["role"]: {"image": row["reference"]} for row in scans}
            services["api"]["environment"] = {"sensitive": marker}
            for image in images:
                image["Config"] = {"Env": [marker]}
            (root / "compose.json").write_text(json.dumps({"services": services}))
            (root / "images.json").write_text(json.dumps(images))
            env = root / "private.env"
            env.write_text("SYNTHETIC=" + marker)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            (artifacts / "image-scan-started-at.txt").write_text(START.isoformat())
            for row in scans:
                (artifacts / ("trivy-" + row["role"] + "-image.json")).write_text(
                    json.dumps(row["report"])
                )
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("release_image_evidence.py", "trivy_cve_inventory.py"):
                (scripts / name).symlink_to(SCRIPTS / name)
            binary = root / "bin"
            binary.mkdir()
            docker = binary / "docker"
            docker.write_text(
                "#!/usr/bin/env python3\nimport sys,pathlib\nname='compose.json' if sys.argv[1]=='compose' else 'images.json'\nprint(pathlib.Path(name).read_text())\n"
            )
            docker.chmod(0o755)
            process_env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"])
            command = [
                "bash",
                str(SCRIPTS / "collect-release-image-evidence.sh"),
                str(env),
                SHA,
                "12345",
            ]
            result = subprocess.run(
                command, cwd=root, env=process_env, capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result_data = json.loads((artifacts / "release-image-evidence.json").read_text())
            self.assertEqual(result_data["source_sha"], SHA)
            self.assertEqual(len(result_data["images"]), 6)
            for path in artifacts.iterdir():
                self.assertNotIn(marker, path.read_text(), path.name)
            # Failed inspection/planning cannot leave an earlier usable success.
            services["keycloak"]["image"] = "quay.io/keycloak/keycloak:latest"
            (root / "compose.json").write_text(json.dumps({"services": services}))
            failed = subprocess.run(
                command, cwd=root, env=process_env, capture_output=True, text=True, check=False
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((artifacts / "release-image-evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
