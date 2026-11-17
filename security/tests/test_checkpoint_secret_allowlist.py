"""Verify the one checkpoint checksum exception cannot suppress other secrets."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    config = root / ".gitleaks.toml"
    target = Path(".ai/checkpoints/CP-AUDIT-AGENDA-06-20261113T052019Z.json")
    metadata = json.loads((root / target).read_text())
    checksum = metadata["visualEvidence"]["fileHashes"]["reports/pmqms-agenda-api-final.log"]
    other = hashlib.sha256(b"Synthetic non-credential negative scanner control").hexdigest()
    prefix, exception = config.read_text().rsplit("\n[[allowlists]]", 1)
    if "Verified SHA256 of agenda API test log" not in exception:
        raise RuntimeError("Review checksum exception ordering before scanning")
    executable = shutil.which("gitleaks")
    if executable is None:
        raise RuntimeError("Pinned Gitleaks scanner is required")
    cases = [
        (target, checksum, True, 1, "without exception checksum is detected"),
        (target, checksum, False, 0, "verified checksum is allowed at exact path"),
        (target, other, False, 1, "different value at same path is detected"),
        (Path("other-metadata.json"), checksum, False, 1, "same value elsewhere is detected"),
    ]
    for path, value, baseline, expected, label in cases:
        with tempfile.TemporaryDirectory(prefix="pmqms-checkpoint-scanner-") as temp:
            folder = Path(temp)
            source = folder / "source"
            destination = source / path
            destination.parent.mkdir(parents=True)
            destination.write_text(json.dumps({"api_key": value}))
            selected = config
            if baseline:
                selected = folder / "baseline.toml"
                selected.write_text(prefix)
            result = subprocess.run(  # noqa: S603 -- installed scanner; fixed flags, owned paths.
                [executable, "dir", "--config", str(selected), "--redact", "--no-banner", "."],
                cwd=source,
                capture_output=True,
                check=False,
            )
            if result.returncode != expected:
                raise RuntimeError(f"{label}: unexpected scanner exit {result.returncode}")
            print("PASS:", label)


if __name__ == "__main__":
    main()
