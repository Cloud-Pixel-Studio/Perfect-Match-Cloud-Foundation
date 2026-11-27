# Security and resilience assessment — 2026-11-25

Scope: authorized Perfect Match QMS repository and synthetic demo at `demo.3-238-70-198.sslip.io`. No production systems or customer data were tested.

## Results

- API test suite: exit 0. Database-dependent tests remain reported as skips by the existing suite; skips are not treated as passes.
- Security regression tests excluding the unavailable scanner integration: 21 passed.
- Web unit tests: 360 passed across 25 files.
- Web lint and TypeScript typecheck: passed.
- Public marketing load probe: 200/200 complete, 0 failed, 0 non-2xx; 20 concurrent clients; 4.14 requests/second; p95 6.321s.
- Health endpoint load probe: 200/200 complete, 0 failed, 0 non-2xx; 20 concurrent clients; 5.84 requests/second; p95 6.014s.
- Response headers observed: CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, restrictive Permissions-Policy, and no-store cache policy on marketing.
- HTTP negative probe: unauthenticated identity routes returned 401, unsupported methods returned 405, traversal encoding returned 400, and no unauthenticated project route was exposed.
- Gitleaks 8.30.1 scanned the worktree and 438 commits. It reported two `generic-api-key` false positives on documentation lines containing SHA-256 hashes; no password/token value was exposed by the redacted report. These findings should be narrowed with a reviewed allowlist or wording change before a release gate.
- The previously reported `minimatch` 10.2.6 advisory (GHSA-g3hv-75wg-m249) was remediated with a workspace-level override to `>=11.0.1`; a fresh `pnpm audit --audit-level high` reports no known vulnerabilities.

## Gaps and blockers

- The pinned OpenGrep binary is not installed in this workspace, so the SAST gate tests fail at setup and no new SAST PASS is claimed.
- Trivy, Checkov, Syft, and ZAP CLIs are not present locally; prior CI/artifact findings remain authoritative, including the known Keycloak image vulnerability blocker. No local image/ZAP scanner PASS is claimed for this run. Gitleaks was installed and executed as documented above.
- The load probe is a bounded availability smoke test, not a capacity certification. It does not represent many authenticated tenants, writes, file uploads, database contention, or a production traffic model.
- Authenticated cross-tenant and project-reference tests could not be completed in this run because the deployed panel remains stuck in its session-loading state after OIDC callback. Direct authenticated identity endpoints respond correctly; UI hydration remains an open defect.

## Decision

Security posture remains **NO-GO for production**. The demo stayed online and unchanged by the probes. Remediation priority is to fix the authenticated frontend hydration issue, install/pin the scanner toolchain in CI, then run tenant-negative tests and an isolated staged capacity test with explicit thresholds.
