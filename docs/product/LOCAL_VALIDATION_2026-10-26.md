# Local validation — 2026-10-26

Outcome: **PARTIAL**. Base commit: 889a5f12e48104a9a612646063035525a8f0dabd.
These results apply to the main-derived local branch, not the unmerged PMC-04 code.

## Environment and observed results

- macOS arm64; workspace-local Node 24.20.0, pnpm 12.3.4, uv 0.13.5;
  uv-managed Python 3.12.15. Existing global Node remains unchanged.
- `pnpm install --frozen-lockfile` and `uv sync --frozen`: completed.
- Backend Ruff format/lint and mypy: passed; mypy checked 22 source files.
- Backend pytest: 25 passed, 44 skipped, two upstream deprecation warnings.
  All 44 skipped cases require disposable PostgreSQL; they are not passes.
- Frontend lint, TypeScript, three tests across two files and production build:
  passed. This does not prove authenticated end-to-end behavior.
- Docker and full application runtime remain unavailable. RLS/tenant isolation,
  organization database integrity, image scans, ZAP and recovery were not run.
- No full security checkpoint or production-readiness claim.

Homebrew installation was stopped after it proposed a large source-build and
dependency upgrade chain on this macOS version. The project toolchain was instead
installed under ignored `artifacts/tooling/`; no application dependency lockfile
was intentionally changed. Docker/Colima were not installed.

Use `./scripts/with-local-tools.sh <command>` for the workspace toolchain, e.g.
`./scripts/with-local-tools.sh pnpm test` or
`./scripts/with-local-tools.sh make typecheck`.

## Checkpoint correction

The existing local checkpoint ran only the tenant-isolation harness and omitted
the organization regression harness required by CI. It now runs audit integrity
(which includes tenant isolation) and organization integrity. Shell syntax was
validated; execution of these Docker-dependent gates remains pending.

## Workflow PR evidence

GitHub reports success for PMC-04 head
e2cdff8abc8781e6f3e246abec08d1db8f2540ea:
- Quality run: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/34439019052
- Security run: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/34439019035

Initial source inspection covered architecture, service transitions, API inputs
and migration guards. The code includes row locking, expected instance versions,
assignment checks, forced RLS and published-configuration guards. This is not a
complete security review or approval. Domain-specific approval independence and
document-release authority must be designed and tested by the document module;
generic assignment eligibility alone does not establish those controls.

Next: provide Docker-compatible local runtime, run the skipped database suites,
then finish PMC-04 review before building the document/evidence lifecycle.
