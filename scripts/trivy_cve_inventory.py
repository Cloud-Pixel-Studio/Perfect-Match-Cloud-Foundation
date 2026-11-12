#!/usr/bin/env python3
"""Generate a deterministic, fail-closed inventory from Trivy vulnerability JSON."""
import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = {"HIGH", "CRITICAL"}


def inventory(report: object, image: str) -> list[dict]:
    if not isinstance(report, dict) or not isinstance(report.get("Results"), list) or not report["Results"]:
        raise ValueError("Trivy report must contain a non-empty Results array")
    rows = []
    for result in report["Results"]:
        if not isinstance(result, dict):
            raise ValueError("Trivy Results entries must be objects")
        if not isinstance(result.get("Target", ""), str):
            raise ValueError("Trivy Target must be a string")
        vulns = result.get("Vulnerabilities", [])
        if vulns is None:
            vulns = []
        if not isinstance(vulns, list):
            raise ValueError("Trivy Vulnerabilities must be an array or null")
        for vuln in vulns:
            if not isinstance(vuln, dict):
                raise ValueError("Trivy vulnerability must be an object")
            severity = vuln.get("Severity")
            if not isinstance(severity, str) or severity not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                raise ValueError("Trivy vulnerability has invalid or missing Severity")
            if severity not in SEVERITIES:
                continue
            required = ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
            if any(not isinstance(vuln.get(k), str) or not vuln[k] for k in required):
                raise ValueError("HIGH/CRITICAL vulnerability missing required metadata")
            fixed = vuln.get("FixedVersion", "")
            if not isinstance(fixed, str):
                raise ValueError("FixedVersion must be a string")
            rows.append({
                "image": image,
                "target": result.get("Target", ""),
                "cve": vuln["VulnerabilityID"],
                "package": vuln["PkgName"],
                "installed_version": vuln["InstalledVersion"],
                "fixed_version": fixed,
                "severity": vuln["Severity"],
            })
    return sorted(rows, key=lambda r: (r["image"], r["target"], r["cve"], r["package"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", required=True, nargs=2, metavar=("IMAGE_DIGEST", "TRIVY_JSON"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        findings = []
        for image, path in args.report:
            if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
                raise ValueError("image reference must include an immutable sha256 digest")
            findings.extend(inventory(json.loads(Path(path).read_text(encoding="utf-8")), image))
        result = {"schema_version": 1, "high_or_critical_count": len(findings), "findings": sorted(findings, key=lambda r: (r["image"], r["target"], r["cve"], r["package"]))}
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Recorded {len(findings)} HIGH/CRITICAL findings in {args.output}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Inventory generation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
