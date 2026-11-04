# Initial defensive security audit — 2026-11-02

Passing automation is evidence, not proof of security or compliance. The release
gate remains **FAIL**.

## Strengths verified

- OIDC Authorization Code + PKCE S256, state, nonce and login binding.
- Opaque hashed sessions, expiry/revocation, HttpOnly cookies, CSRF double-submit
  and same-origin validation.
- Tenant context derived server-side, composite tenant/unit keys, forced RLS and a
  runtime database role without `BYPASSRLS`.
- Unit-scoped QMS capabilities separate from tenant role, seat and ownership.
- Append-only transactional audit, expected versions and database workflow guards.
- Private object storage, controlled PDF intake, hashes, quarantine and fail-closed
  malware scanning.
- SHA-pinned GitHub Actions, OpenGrep, Gitleaks, Trivy, dependency audits, SBOM,
  license policy and passive ZAP workflow.

## Prioritized findings

| Severity | Finding | Exploitability / impact | Effort |
| --- | --- | --- | --- |
| Critical operational | 143 untracked paths are not protected by GitHub review or CI | Local loss or unreviewed publication could remove or expose most product work | Medium |
| High release | Fresh scans find five unique High findings in Keycloak 26.8.1 and one High in SeaweedFS 4.51 | No Critical finding remains; fixed stable images are not yet available for every finding | Medium |
| Resolved in worktree | `joserfc 1.7.5` was flagged as CVE-2026-119284 | Updated only this package to 1.7.7; `pip-audit`, identity/bootstrap tests, Ruff and mypy pass | Completed |
| High | No production TLS, enforced MFA, secrets manager, backup schedule, RPO/RTO, monitoring or incident runbook | Account/data compromise and unrecoverable outage risk | High |
| Resolved locally | Code and runtime migration mismatch | Runtime recovered with the protected environment and migrated from 0038 to 0039 after a verified CP-04 restore | Completed |
| High | No authenticated DAST or pentest in approved staging | IDOR, authorization and workflow defects may remain undiscovered | Medium |
| Medium | `minimatch` moderate ReDoS advisory in development lint dependencies | CI/developer DoS exposure, not application runtime | Low |
| Medium | Six custom OpenGrep rules found zero issues, but one file parsed partially | Limited rule coverage and an analysis blind spot | Low |
| Medium | Session-command flags guard workflows but the runtime role could set them after SQL injection | Useful integrity boundary, not a substitute for injection prevention | Medium |
| Medium | No completed ASVS 5 / ISO 27001 / NIST CSF evidence mapping | Claims cannot be substantiated or audited | Medium–High |
| Human review | ISO publications/mappings and commercial license behavior | Legal/content and entitlement risk | High |

Current direct checks: Gitleaks worktree/history PASS, OpenGrep zero findings with
the limitations above, web lint/typecheck/21 tests PASS, `git diff --check` PASS,
Node audit has no high/critical and one moderate, and Python audit has no known
vulnerability after the focused JOSE update. API Ruff format/lint and strict mypy
pass for 53 sources; six identity/bootstrap tests and the disposable PostgreSQL
suite of 183 tests pass. Fresh runtime scans report zero High/Critical for the API,
web, PostgreSQL and ClamAV images. API and web now run as non-root with read-only
root filesystems, all Linux capabilities dropped, `no-new-privileges`, bounded
process counts and isolated temporary filesystems. The branch is not release-ready
because upstream image, production-control and review findings remain.

The refreshed Keycloak scan finds CVE-2026-91403 and CVE-2026-91415 in OpenJDK,
CVE-2026-102554 in Guava, and CVE-2026-119373/CVE-2026-119586 in `sqlite-libs`.
The Java and vulnerability databases were downloaded fresh on 2026-11-02. The
report contains no Critical finding; Guava and CVE-2026-91415 have a stated fixed
version, while the selected vendor feed does not state one for the other three.
Keycloak 26.8.1 was the current official release when checked. SeaweedFS
4.51 contains CVE-2026-116587 in go-jose; upstream released source 4.52, but the
normal `4.52` container tag was not available when verified. Do not substitute a
development or specialty storage image merely to make the scanner gate green.

## Required gates before a PR

1. Secret scan of worktree and full history.
2. Formatting, lint, strict types, unit and disposable PostgreSQL integrity suites.
3. Migration upgrade/downgrade/restore tests with tenant and role review.
4. SAST plus CodeQL; dependency and image scans with explicit reachability triage.
5. CycloneDX SBOMs tied to the exact commit and image digests.
6. Playwright/axe and visual regression for UI changes.
7. Authenticated ZAP only against an explicitly approved isolated staging system.
8. Independent review, rollback evidence and human approval.

Wazuh remains optional for future hosted telemetry; it is not a substitute for
application audit or observability. Checkov is appropriate when real IaC exists.
Do not install operational platforms before the deployment architecture is chosen.
