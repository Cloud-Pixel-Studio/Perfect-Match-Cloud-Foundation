"""Check exact audit digest exceptions without suppressing other values/paths."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    config = root / ".gitleaks.toml"
    blocks = tomllib.loads(config.read_text())["allowlists"]
    selected = [b for b in blocks if b["description"].startswith("Four verified baseline source")]
    if len(selected) != 1:
        raise RuntimeError("Exactly one architecture checksum exception is required")
    block = selected[0]
    if block["condition"] != "AND" or block["targetRules"] != ["generic-api-key"]:
        raise RuntimeError("Checksum exception must constrain both path and value")
    target = Path("docs/audits/2026-11-14/ARCHITECTURE_ACCESS_INVENTORY.json")
    if block["paths"] != [r"(^|/)docs/audits/2026-11-14/ARCHITECTURE_ACCESS_INVENTORY\.json$"]:
        raise RuntimeError("Unexpected checksum exception path")
    values = [v.removeprefix("^").removesuffix("$") for v in block["regexes"]]
    if len(set(values)) != 4 or any(len(v) != 64 for v in values):
        raise RuntimeError("Exactly four SHA256 values are required")
    baseline = "8133bac47a0731c31738d942f131b17902bb6fe5"
    files = [
        "apps/api/src/pmc_api/auth.py",
        "apps/api/src/pmc_api/qms_access.py",
        "apps/api/src/pmc_api/tenant_access.py",
        "apps/web/src/components/qms-access-workspace.tsx",
    ]
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git required for baseline source validation")
    hashes = {
        hashlib.sha256(
            subprocess.check_output([git, "show", f"{baseline}:{p}"], cwd=root)  # noqa: S603 -- fixed baseline and paths
        ).hexdigest()
        for p in files
    }
    if set(values) != hashes:
        raise RuntimeError("Exceptions must match the verified baseline source files")
    scanner = shutil.which("gitleaks")
    if not scanner:
        raise RuntimeError("Pinned Gitleaks required")
    control = hashlib.sha256(b"Synthetic noncredential audit checksum control").hexdigest()
    cases = (
        [(target, v, 0) for v in values]
        + [(Path("other.json"), v, 1) for v in values]
        + [(target, control, 1)]
    )
    for path, value, expected in cases:
        with tempfile.TemporaryDirectory(prefix="pmqms-audit-checksum-") as tmp:
            source = Path(tmp) / path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(json.dumps({"api_key": value}))
            result = subprocess.run(  # noqa: S603 -- installed scanner; fixed flags, owned paths
                [
                    scanner,
                    "dir",
                    "--config",
                    str(config),
                    "--redact",
                    "--no-banner",
                    ".",
                ],
                cwd=tmp,
                capture_output=True,
                check=False,
            )
            if result.returncode != expected:
                raise RuntimeError("Audit checksum scanner control failed")
    print("PASS: four baseline hashes, four off-path controls and one different-value control")


if __name__ == "__main__":
    main()
