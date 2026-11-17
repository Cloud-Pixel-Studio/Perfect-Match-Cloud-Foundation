"""Reconcile audit-only JUnit, function-entry traces, HTTP metadata and source routes.

Run from repository root. Never infer HTTP success from a Python function call.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path.cwd()
artifacts = root / "artifacts/module-operability-20261114"
out = root / "docs/audits/2026-11-14"
sys.path.insert(0, str(root / "apps/api/src"))
from pmc_api.main import app


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


suites = []
passed_ids: set[str] = set()
for path in sorted(artifacts.glob("*.xml")):
    tests = []
    outcomes = []
    states: Counter[str] = Counter()
    for case in ET.parse(path).iter("testcase"):
        skipped = case.find("skipped")
        if skipped is not None:
            state = (
                "xfailed" if skipped.attrib.get("type") == "pytest.xfail" else "skipped"
            )
        elif case.find("failure") is not None or case.find("error") is not None:
            state = "failed"
        else:
            state = "passed"
        states[state] += 1
        nodeid = (
            case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        )
        outcomes.append({"test_id": nodeid, "state": state})
        if state == "passed":
            passed_ids.add(nodeid)
            tests.append(nodeid)
    suites.append(
        {
            "suite": path.stem,
            "result": dict(states),
            "passed_tests": tests,
            "outcomes": outcomes,
            "junit_artifact": str(path.relative_to(root)),
            "junit_sha256": sha(path),
        }
    )

calls: dict[str, set[str]] = {}
for path in sorted(artifacts.glob("*-calls.json")):
    for key, values in json.loads(path.read_text())["calls"].items():
        calls.setdefault(key, set()).update(set(values) & passed_ids)

routes = []
for path in sorted((root / "apps/api/src/pmc_api").glob("*.py")):
    tree = ast.parse(path.read_text())
    prefix = ""
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "APIRouter"
        ):
            prefix = next(
                (k.value.value for k in node.value.keywords if k.arg == "prefix"),
                "",
            )
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr in {"get", "post", "patch", "put", "delete"}
            ):
                routes.append(
                    {
                        "module": path.stem,
                        "method": dec.func.attr.upper(),
                        "path": prefix + dec.args[0].value,
                        "function": f"{path.name}:{node.name}",
                        "source": str(path.relative_to(root)),
                        "line": node.lineno,
                    }
                )
for action in ("submit", "approve", "reject", "release"):
    routes.append(
        {
            "module": "documents",
            "method": "POST",
            "path": f"/documents/{{document_id}}/revisions/{{revision_id}}/{action}",
            "function": "documents.py:_endpoint_factory.<locals>.endpoint",
            "source": "apps/api/src/pmc_api/documents.py",
            "line": 552,
            "factory_action": action,
        }
    )
schema = app.openapi()
openapi_pairs = {
    (method.upper(), path)
    for path, item in schema["paths"].items()
    for method in item
    if method in {"get", "post", "put", "patch", "delete"}
}
assert {(route["method"], route["path"]) for route in routes} == openapi_pairs
http = json.loads((artifacts / "module-http-operations.json").read_text())
for route in routes:
    ids = sorted(calls.get(route["function"], []))
    route["observation"] = (
        "route_function_observed_in_passing_test"
        if ids
        else "route_function_not_observed"
    )
    route["passed_test_ids"] = ids
    route["evidence_limit"] = (
        "Function entry may be denied/error/direct Python call. It is not successful HTTP "
        "or branch coverage. Shared document factory is not disambiguated by function trace."
    )
    pattern = re.compile(
        "^"
        + "/".join(
            "[^/]+" if part.startswith("{") else re.escape(part)
            for part in route["path"].split("/")
        )
        + "$"
    )
    successes = []
    for case in http:
        if case["test_id"] not in passed_ids:
            continue
        for operation in case["operations"]:
            if (
                operation["method"] == route["method"]
                and pattern.fullmatch(operation["path"])
                and 200 <= operation["status"] < 300
            ):
                successes.append(
                    {
                        "test_id": case["test_id"],
                        "role": operation["role"],
                        "status": operation["status"],
                    }
                )
    route["successful_http_observations"] = successes
    route["http_evidence_limit"] = (
        "Only dedicated synthetic TestClient/SQL tests, AV/S3 in memory. A 2xx here "
        "does not validate every role/state, browser, OIDC or external services."
    )

api_unit = next(suite for suite in suites if suite["suite"] == "api-unit")
counts = {
    "unique_pytest_passed": len(passed_ids),
    "database_passed": sum(
        s["result"].get("passed", 0) for s in suites if s["suite"] != "api-unit"
    ),
    "database_xfailed_known_defects_not_passed": sum(
        s["result"].get("xfailed", 0) for s in suites
    ),
    "api_unit_passed": api_unit["result"]["passed"],
    "api_unit_skipped_not_passed": api_unit["result"]["skipped"],
    "web_unit_passed": 60,
    "product_operations": len(routes),
    "openapi_paths": len(schema["paths"]),
    "route_observations": dict(Counter(r["observation"] for r in routes)),
    "route_positive_http_observed_dedicated_tests": sum(
        bool(r["successful_http_observations"]) for r in routes
    ),
    "function_entries_observed": sum(bool(ids) for ids in calls.values()),
}
assert counts["database_passed"] == 452, counts
assert counts["unique_pytest_passed"] == 502, counts
assert counts["database_xfailed_known_defects_not_passed"] == 2, counts


def files(paths):
    return [
        {"path": str(p.relative_to(root)), "sha256": sha(p), "bytes": p.stat().st_size}
        for p in sorted(paths)
        if p.is_file()
    ]


data = {
    "audit_date": "2026-11-14",
    "branch": "codex/audit-module-operability",
    "base_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip(),
    "source_checkpoint": "CP-MODULE-AUDIT-00-20261114T184106Z",
    "handoff_checkpoint": "CP-MODULE-HANDOFF-00-20261114T204719Z",
    "scope": "Audit tests/reports and narrow verified-checksum scanner gate; disposable synthetic PostgreSQL. No local/prod DB migration, browser or real S3/ClamAV/OIDC claim.",
    "execution": {
        "image": "sha256:f43c10c086d4f4576c0eefd9de52916a3a5931e6e01fff571e84a981b5889df3",
        "database_ports": [55468, 55469, 55470, 55471, 55472, 55473, 55474, 55477],
        "tmpfs": "/var/lib/postgresql:rw,nosuid,nodev,size=512m",
        "wrapper": "/Users/Gerdel_Garcia/Documents/ChatGPT/SaaS QMS PerfectMatchSystems/scripts/with-local-tools.sh",
        "harness": "docs/audits/2026-11-14/module-operability-evidence/run-module-http-integrity.sh",
        "harness_transformations": [
            "Reuse installed PostgreSQL image",
            "Disposable tmpfs/owned loopback port",
            "JUnit and audit-only metadata without headers/tokens/bodies",
        ],
        "incidents": [
            "Initial instrumented tenant-isolation attempt produced no evidence; unchanged full retry passed27.",
            "Initial HTTP3FAIL: minimal-reviewer404 real M01; record_event patch target was fixture error.",
            "Retry1: list query parameter control_instance_id was fixture error; corrected to instance_id.",
            "Retry2: privileged fixture revocation lacked actor context; replaced with normal owner HTTP revoke and HTTP tenant selection.",
        ],
    },
    "counts": counts,
    "suites": suites,
    "routes": sorted(routes, key=lambda r: (r["path"], r["method"])),
    "function_entry_observations": [
        {
            "function": key,
            "passed_test_count": len(ids),
            "sample_test_ids": sorted(ids)[:10],
            "sample_truncated": len(ids) > 10,
            "limit": "Entry only; not branch/HTTP success coverage.",
        }
        for key, ids in sorted(calls.items())
        if ids
    ],
    "http_operations": http,
    "known_defects": [
        {
            "id": "M01",
            "severity": "P2 functional/least privilege",
            "status": "OPEN_REPRODUCED_NOT_FIXED",
            "expected_failures": [
                case["test_id"]
                for suite in suites
                for case in suite["outcomes"]
                if case["state"] == "xfailed"
            ],
            "evidence": "Read/review/approve-only actor sees revision but parent SELECT FOR UPDATE is invisible under UPDATE RLS. Reject and approve return404; revision/ledger unchanged.",
            "positive_test_limit": "Independent reviewer has explicit additional documents.release in positive lifecycle fixtures. This is a disclosed test actor, not a recommended product workaround or grant change.",
        }
    ],
    "committed_logs": files((out / "module-operability-evidence").glob("*.log")),
    "raw_artifacts": files(artifacts.rglob("*")),
    "trace_plugin": {
        "path": "docs/audits/2026-11-14/module-operability-evidence/module_audit_trace.py",
        "sha256": sha(out / "module-operability-evidence/module_audit_trace.py"),
        "limitations": "sys.setprofile/threading.setprofile record function entry only; no arguments. JUnit PASS filter. No statement/branch/assertion coverage.",
    },
}
(out / "MODULE_OPERABILITY_EVIDENCE.json").write_text(json.dumps(data, indent=2) + "\n")
lines = [
    "# Inventario de operaciones API — 14 noviembre 2026",
    "",
    "180 operaciones de producto/131paths:176decoradas+4comandos documentales de fábrica. No incluye /openapi.json del framework.",
    "",
    "Entrada observada puede ser denegación/error/llamada Python directa: no acredita éxito HTTP ni todos los estados. La columna HTTP cuenta únicamente respuestas2xx de los tres casos dedicados PASS, con SQL aislado y AV/S3 en memoria. M01 conserva dos XFAILstrict, nunca PASS.",
    "",
    "| Módulo | Operación | Función | Entrada observada | Casos PASS con HTTP2xx acotado |",
    "| --- | --- | --- | --- | ---: |",
]
for route in data["routes"]:
    status = (
        "Sí, acotada"
        if route["passed_test_ids"]
        else "No; implementada sin esta observación"
    )
    positive = len({item["test_id"] for item in route["successful_http_observations"]})
    lines.append(
        f"| {route['module']} | `{route['method']} {route['path']}` | `{route['function']}` | {status} | {positive} |"
    )
(out / "MODULE_OPERABILITY_ROUTES.md").write_text("\n".join(lines) + "\n")
print(json.dumps(counts))
