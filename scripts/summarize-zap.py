#!/usr/bin/env python3
"""Create complete, disposition-preserving evidence from ZAP baseline output."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SEVERITIES = {"0": "informational", "1": "low", "2": "medium", "3": "high"}


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: summarize-zap.py ZAP_JSON ZAP_LOG OUTPUT_JSON", file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        log = Path(argv[2]).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ZAP evidence validation failed: {exc}", file=sys.stderr)
        return 1

    summary_line = re.findall(
        r"FAIL-NEW:\s*(\d+).*?WARN-NEW:\s*(\d+).*?PASS:\s*(\d+)",
        log,
        flags=re.DOTALL,
    )
    if not summary_line:
        print("ZAP baseline disposition summary missing.", file=sys.stderr)
        return 1
    fail, warn, passed = map(int, summary_line[-1])

    counts = {name: 0 for name in SEVERITIES.values()}
    alerts: list[dict[str, object]] = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            risk_code = str(alert.get("riskcode", ""))
            severity = SEVERITIES.get(risk_code)
            if severity is None:
                print(f"Unknown ZAP risk code: {risk_code}", file=sys.stderr)
                return 1
            count = int(alert.get("count", 0))
            counts[severity] += count
            alerts.append(
                {
                    "pluginid": str(alert.get("pluginid", "")),
                    "title": alert.get("alert", ""),
                    "risk": alert.get("riskdesc", ""),
                    "risk_code": risk_code,
                    "confidence": alert.get("confidence", ""),
                    "count": count,
                    "urls": [
                        instance.get("uri", "")
                        for instance in alert.get("instances", [])
                    ],
                    "evidence": [
                        instance.get("evidence", "")
                        for instance in alert.get("instances", [])
                        if instance.get("evidence")
                    ],
                }
            )

    output = {
        "baseline": {"pass": passed, "warn": warn, "fail": fail},
        "severity": counts,
        "alerts": alerts,
        "zap_version": report.get("@version", ""),
    }
    Path(argv[3]).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    if counts["high"] != 0:
        print("High-risk ZAP findings detected.", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
