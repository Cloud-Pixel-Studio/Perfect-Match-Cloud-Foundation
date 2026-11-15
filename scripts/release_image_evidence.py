#!/usr/bin/env python3
"""Bind six vulnerability reports to inspected images; never authorize deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from trivy_cve_inventory import inventory

ROLES = {"api", "web", "postgres", "seaweedfs", "keycloak", "clamav"}
REPOSITORIES = {
    "seaweedfs": "chrislusf/seaweedfs",
    "keycloak": "quay.io/keycloak/keycloak",
    "clamav": "clamav/clamav",
}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")


def timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("scan timestamp must be a nonempty ISO8601 string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("scan timestamp requires a timezone")
    return result.astimezone(timezone.utc)


def duplicate_free(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key in scanner evidence")
        result[key] = value
    return result


def read_json(path: Path) -> tuple[Any, str]:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("scanner evidence exceeds the 64MiB limit")
    raw = path.read_bytes()

    def invalid_constant(_value: str) -> None:
        raise ValueError("nonfinite JSON number in scanner evidence")

    return json.loads(
        raw, object_pairs_hook=duplicate_free, parse_constant=invalid_constant
    ), hashlib.sha256(raw).hexdigest()


def normalized_digest(reference: str) -> str:
    name, digest = reference.rsplit("@", 1)
    repository = name.rsplit(":", 1)[0] if ":" in name.rsplit("/", 1)[-1] else name
    return repository + "@" + digest


def validate_reference(role: str, reference: str, source_sha: str) -> None:
    if role in {"api", "web"}:
        if reference != f"pmcloud-{role}:{source_sha}":
            raise ValueError("application reference must match the exact source SHA")
    elif role == "postgres":
        if reference != "pmcloud-postgres:local":
            raise ValueError("unexpected PostgreSQL image reference")
    else:
        if not re.fullmatch(
            re.escape(REPOSITORIES[role])
            + r":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}@sha256:[0-9a-f]{64}",
            reference,
        ):
            raise ValueError(
                "vendor image requires the expected repository and pinned manifest digest"
            )


def compose_vendor_references(config: object) -> dict[str, str]:
    if not isinstance(config, dict) or not isinstance(config.get("services"), dict):
        raise ValueError("Compose configuration must contain services")
    result: dict[str, str] = {}
    for role in ("seaweedfs", "keycloak", "clamav"):
        service = config["services"].get(role)
        reference = service.get("image") if isinstance(service, dict) else None
        if not isinstance(reference, str):
            raise ValueError("required vendor image is missing from Compose")
        validate_reference(role, reference, "0" * 40)
        result[role] = reference
    return result


def strings(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("image tags/digests must be arrays of strings")
    return value


def bind_report(
    report: object, inspected: list[dict[str, Any]], reference: str, start: datetime, now: datetime
) -> tuple[dict[str, Any], int]:
    if (
        not isinstance(report, dict)
        or report.get("SchemaVersion") != 2
        or report.get("ArtifactType") != "container_image"
        or report.get("ArtifactName") != reference
    ):
        raise ValueError("scanner report artifact does not match the requested container image")
    created = timestamp(report.get("CreatedAt"))
    if created < start or created > now + timedelta(seconds=30):
        raise ValueError("scanner report is stale or has a future timestamp")
    remote = "@" in reference
    expected = normalized_digest(reference) if remote else reference
    field = "RepoDigests" if remote else "RepoTags"
    matches = [item for item in inspected if expected in strings(item.get(field))]
    if len(matches) != 1:
        raise ValueError("image inspection does not uniquely identify the requested reference")
    actual = matches[0]
    metadata = report.get("Metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("ImageID") != actual["Id"]
        or expected not in strings(metadata.get(field))
    ):
        raise ValueError("scanner image ID/reference differs from the inspected image")
    config = metadata.get("ImageConfig")
    if (
        not isinstance(config, dict)
        or config.get("architecture") != actual.get("Architecture")
        or config.get("os") != actual.get("Os")
    ):
        raise ValueError("scanner image platform differs from inspected image")
    results = report.get("Results")
    if not isinstance(results, list) or not any(
        isinstance(row, dict) and row.get("Class") in {"os-pkgs", "lang-pkgs"} for row in results
    ):
        raise ValueError("scanner report contains no vulnerability package target")
    secret_count = 0
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("scanner target must be an object")
        secrets = result.get("Secrets", [])
        if secrets is None:
            secrets = []
        if not isinstance(secrets, list):
            raise ValueError("scanner secret findings must be an array or null")
        for finding in secrets:
            if not isinstance(finding, dict) or finding.get("Severity") not in {
                "UNKNOWN",
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
            }:
                raise ValueError("invalid secret finding severity")
            secret_count += finding["Severity"] in {"HIGH", "CRITICAL"}
    return {
        "image_id": actual["Id"],
        "identity_kind": "docker_configuration_digest",
        "registry_reference": expected if remote else None,
        "platform": {"os": actual["Os"], "architecture": actual["Architecture"]},
        "report_created_at": created.isoformat(),
    }, secret_count


def build_evidence(
    inspected: object,
    scans: list[dict[str, Any]],
    source_sha: str,
    run_id: str,
    start: datetime,
    now: datetime,
) -> dict[str, Any]:
    if not SHA.fullmatch(source_sha) or not run_id.isdigit() or int(run_id) <= 0:
        raise ValueError("exact source SHA and workflow run ID required")
    if start > now + timedelta(seconds=30) or now - start > timedelta(hours=1):
        raise ValueError("scan window is invalid or older than one hour")
    if (
        not isinstance(inspected, list)
        or len(inspected) != 6
        or any(not isinstance(row, dict) for row in inspected)
    ):
        raise ValueError("inspection must contain exactly six images")
    if any(
        not isinstance(row.get("Id"), str)
        or not DIGEST.fullmatch(row["Id"])
        or row.get("Os") != "linux"
        or row.get("Architecture") not in {"amd64", "arm64"}
        for row in inspected
    ):
        raise ValueError("invalid inspected image ID or platform")
    if len({row["Id"] for row in inspected}) != 6:
        raise ValueError("six distinct inspected image IDs required")
    roles = [row.get("role") for row in scans]
    if len(roles) != 6 or set(roles) != ROLES:
        raise ValueError("six unique required image roles must be scanned")
    if len({row["path"] for row in scans}) != 6:
        raise ValueError("scanner report cannot be reused for another image role")
    images, findings, secret_count = [], [], 0
    for scan in sorted(scans, key=lambda row: row["role"]):
        role, reference = scan["role"], scan["reference"]
        validate_reference(role, reference, source_sha)
        identity, secret_total = bind_report(scan["report"], inspected, reference, start, now)
        rows = inventory(scan["report"], reference)
        secret_count += secret_total
        findings.extend({"role": role, **row} for row in rows)
        images.append(
            {
                "role": role,
                "reference": reference,
                **identity,
                "report_sha256": scan["sha256"],
                "report_file": Path(scan["path"]).name,
                "high_or_critical": len(rows),
                "secret_high_or_critical": secret_total,
            }
        )
    if {row["image_id"] for row in images} != {row["Id"] for row in inspected}:
        raise ValueError("all six inspected images must be uniquely bound to their roles")
    return {
        "schema_version": 1,
        "source_sha": source_sha,
        "workflow_run_id": run_id,
        "scan_started_at": start.isoformat(),
        "generated_at": now.isoformat(),
        "integrity_verified": True,
        "production_authorized": False,
        "high_or_critical_count": len(findings),
        "secret_high_or_critical_count": secret_count,
        "images": images,
        "findings": findings,
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".release-images-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--scan-started-at", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--report", action="append", nargs=3, required=True, metavar=("ROLE", "REFERENCE", "JSON")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = {
            args.inspection.resolve(),
            args.scan_started_at.resolve(),
            *(Path(row[2]).resolve() for row in args.report),
        }
        if args.output.resolve() in inputs:
            raise ValueError("output must not overwrite input evidence")
        args.output.unlink(missing_ok=True)
        inspected, inspection_hash = read_json(args.inspection)
        scans = []
        for role, reference, name in args.report:
            path = Path(name)
            report, checksum = read_json(path)
            scans.append(
                {
                    "role": role,
                    "reference": reference,
                    "path": str(path.resolve()),
                    "report": report,
                    "sha256": checksum,
                }
            )
        payload = build_evidence(
            inspected,
            scans,
            args.source_sha,
            args.run_id,
            timestamp(args.scan_started_at.read_text().strip()),
            datetime.now(timezone.utc),
        )
        payload["inspection_sha256"] = inspection_hash
        write_atomic(args.output, payload)
        print(
            f"Bound 6 images; HIGH/CRITICAL={payload['high_or_critical_count']}; secret HIGH/CRITICAL={payload['secret_high_or_critical_count']}; not production authorization"
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Release image evidence failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
