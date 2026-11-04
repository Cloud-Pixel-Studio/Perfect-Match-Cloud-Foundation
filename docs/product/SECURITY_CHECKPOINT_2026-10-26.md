# Security checkpoint — 2026-10-26

## Follow-up: Keycloak image triage — 2026-10-28

The local-only Keycloak image is pinned to 26.8.1. Pulling its official tag on
2026-10-28 returned the same digest already in use, so no rebuilt upstream
image was available by tag. Trivy against that exact digest reports two HIGH
OpenJDK findings, CVE-2026-91403 and CVE-2026-91415, in
`java-21-openjdk-headless` `21.0.12.1.1-1.2.el9`, with no fixed version listed;
it also reports a HIGH Guava finding with upstream fix `33.7.2`. Do not suppress
these results or replace Keycloak's bundled Java dependencies independently.

Red Hat describes CVE-2026-91403 as weak eMudhra intermediate certificates and
notes that non-portable RHEL OpenJDK uses the system CA package; CVE-2026-91415
is an OpenJDK 2D out-of-bounds write. This does not prove exploitability in the
local identity-provider configuration. Keycloak remains disposable and local;
production identity-provider selection, configuration, and security review are
still open. Release security remains FAIL. References: [Keycloak 26.8.1
release](https://www.keycloak.org/2026/10/keycloak-2681-released), [Red Hat
CVE-2026-91403](https://access.redhat.com/security/cve/cve-2026-91403), [Red Hat
CVE-2026-91415](https://access.redhat.com/security/cve/cve-2026-91415).

## Follow-up: SeaweedFS image triage — 2026-10-28

Trivy on the pinned SeaweedFS 4.51 digest reports four findings in the bundled
Go binary: HIGH `CVE-2026-116587` (`go-jose` 4.1.5; fixed in 4.1.6), UNKNOWN
`CVE-2026-78661` and `CVE-2026-97045` (`x/net` 0.61.0; fixed in 0.62.0), and
UNKNOWN `GO-2026-5932` (`x/crypto` 0.58.0; no known fixed version). The Go
database defines GO-2026-5932 specifically for the unmaintained `openpgp`
packages; Trivy's module inventory does not establish whether those symbols are
reachable in SeaweedFS. Keep this finding open until upstream upgrades the
module or a reachability analysis establishes impact. The upstream release page
lists 4.51 as latest on 2026-10-28 (released Oct 25), so no newer image was
selected. The image remains development storage, not production approval.
References: [SeaweedFS 4.51 release](https://github.com/seaweedfs/seaweedfs/releases),
[Go vulnerability report GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932).

## Latest follow-up: permission management UI

Owner grant/revoke management and personal read-only views are implemented and
were exercised in a real browser against the local API. Grant, duplicate denial,
cancel, revoke and preserved history were verified using fictional data. A
member/auditor saw no management controls; tenant switching reset the displayed
organization and removed the previous tenant's audit panel. Inputs are disabled
during switching and late audit responses are ignored after context changes.

Final development checkpoint PASS: **123 distinct backend cases and 7 frontend
tests** (28 unit, 27 tenant, 17 organization, 30 workflow and 21 QMS access).
The local owner bootstrap has three additional tests proving it cannot run with
missing/staging/production environment labels. Existing members were not elevated.
Frontend lint/types/build, backend checks, configured SAST/fixtures, secret scans,
license checks and runtime health passed. API/web image vulnerability scans
reported zero findings when executed. Raw evidence is in `artifacts/` and the
UI proof is `artifacts/qms-access-panel-verified.png`.

The extra owner account and development site are fictional local fixtures. The
read grant used for the UI test is revoked and retained in history. Browser app
sessions were logged out; production onboarding and MFA are still unfinished.
The two Keycloak/OpenJDK findings remain open and release security remains FAIL.

## Latest follow-up: scoped QMS access

Migration 0008, the QMS access API and its invoker SQL helper now provide explicit
unit-scoped business capabilities. Owners manage grants to other active members;
no platform role or purchased seat automatically grants document authority.
Auditors remain read-only, inactive identities/scopes deny access, and grant
history is retained. Domain modules must still call the capability helper for
the actual resource scope; document lifecycle and process scopes are unfinished.

Latest local `make checkpoint`: **PASS**, with 25 unit backend cases and
27 tenant, 17 organization, 30 workflow and 21 QMS access PostgreSQL cases:
**120 distinct backend tests**, plus **6 frontend tests**. Included are negative
tests for existing foreign-tenant targets, elevation, self-grants, auditor writes,
history mutation/deletion, duplicate grants and rollback when auditing fails.
Runtime identity smoke and repository Trivy checks passed. No remote CI run or
production deployment was performed. Dedicated permission-management UI is pending.

The web proxy UUID-path bug is fixed and tested; valid resource identifiers reach
the API, while unknown roots, traversal and embedded URLs remain rejected. The
integration smoke checks the API's missing-resource response through the proxy.

The Keycloak release gate still fails. Vendor research distinguishes trust-store
and graphics processing findings. Red Hat notes that non-portable RPM OpenJDK
uses the system CA store, but we have not completed trust-store verification for
the exact image; neither advisory is closed or suppressed. References:
[CVE-2026-91403](https://access.redhat.com/security/cve/cve-2026-91403),
[CVE-2026-91415](https://access.redhat.com/security/cve/cve-2026-91415).

**Development checkpoint: PASS. Overall release security gate: FAIL.**
Unresolved third-party image advisories prevent production approval. Neither
certification, full QMS parity nor commercial readiness is claimed.

## Follow-up: PostgreSQL and publication hardening

This follow-up supersedes the PostgreSQL blocker in the historical table below.
The local/CI image is now built from
`infrastructure/local/postgres.Dockerfile`, retaining official PostgreSQL 18 and
its data layout while refreshing Alpine packages and using Alpine `su-exec`
instead of the Go-based `gosu`. It runs as the PostgreSQL OS user by default and
has an image healthcheck. Trivy reports **0 vulnerabilities and 0 failed
configuration checks** for the hardened image/Dockerfile in the scans executed.
Tests and Compose use the same image; CI scans that actual image. Fresh database
initialization, tenant/audit, organization and workflow suites are revalidated.
Do not switch this image to an arbitrary host bind mount without testing ownership.

Publication now locks and refreshes the workflow version before graph validation.
Migration 0007 serializes configuration edits against that lock. One stale
publication regression and the existing-step edit regression failed before their
fixes; all 30 workflow cases now pass, including the insert serialization case.
The distinct backend count increases from 96 to **99**; frontend remains 4.

Remaining security blocker: the two HIGH OpenJDK advisories in Keycloak 26.8.1,
plus explicit triage of lower/unknown third-party observations. Overall release
gate remains FAIL. No vendor patch or safe applicability disposition has been
established for those two high findings. Findings were not hidden or suppressed.

## Source and scope

Local branch `pmc/workflow-hardening`, based on unmerged PMC-04 head
`e2cdff8abc8781e6f3e246abec08d1db8f2540ea`. Changes remain local; no PR merge,
production deployment or repository administration was performed. Main remains
the previous PMC-03 baseline. Read the local diff alongside this evidence.

## Implemented corrections

- Migration 0006 prevents moving published workflow configuration to a draft by
  checking both old and new parent versions. A runtime-role SQL regression failed
  before the fix and passed after it.
- Locked workflow instances refresh ORM identity-map state before validating
  transitions/cancellation. Two preloaded-session regressions failed before the
  fix and passed after it. Existing concurrent-writer checks remain passing.
- Browser CSP uses fresh cryptographic nonces and dynamic rendering, with no
  production unsafe-inline/eval. Incoming policies/nonces are replaced. Runtime
  HTML checks confirmed matching nonces on every script and different nonces on
  successive requests. Added COOP, COEP and CORP headers; removed inline tree
  indentation styles in favor of CSS.
- Updated Next/eslint-config-next to 16.4.3, Vitest to 5.0.3 and affected
  transitive packages. Updated certifi, urllib3, Mako and development pytest,
  preserving regenerated lockfiles and hashed runtime requirements.
- Fixed macOS-incompatible environment-file editing, preserving permissions and
  existing secrets across repeat runs. Added API Docker context exclusions.
- Local checkpoint now runs audit/tenant, organization and workflow DB harnesses.
- CI now rejects HIGH/CRITICAL findings in third-party images and rejects missing
  report structure. These CI edits have been validated locally, not run remotely.

## Observed validation

| Check | Observed result |
| --- | --- |
| `make checkpoint` through local tool wrapper | PASS; full scanner gate remains separate |
| Backend unit suite | 25 passed; DB suites run separately rather than counted as skipped passes |
| Tenant isolation harness | 27 passed |
| Organization harness and migration regression | 17 passed; unsafe downgrade rejected |
| Workflow harness and migration round-trip | 27 passed; unsafe historical downgrade rejected |
| Frontend tests | 4 passed across 3 files |
| Ruff, mypy, frontend lint/types/build, ShellCheck | PASS |
| pnpm audit / pip-audit | No known vulnerabilities reported after updates |
| OpenGrep + custom fixtures | PASS, 0 findings under configured six rules; not comprehensive proof |
| Gitleaks working tree/history | No leaks found; history scanned 75 commits |
| Trivy repository including development deps | 0 vulnerability findings; 0 failed misconfig checks |
| API/frontend final images | 0 vulnerability findings in scans executed |
| Dependency license policy | PASS; Python 56, Node 12 license entries in policy report |
| CycloneDX | Repository/API/frontend SBOMs generated |
| ZAP passive hardened UI | 66 passed, 2 informational warnings, 0 failed dispositions; 0 low/medium/high instances |
| Runtime health | API, web, PostgreSQL, Keycloak and SeaweedFS healthy |
| Identity integration smoke | OIDC, tenant denial, CSRF, member denial, web proxy and logout PASS |
| Object storage smoke | Write/read/delete PASS; anonymous access DENIED |

ZAP warnings are Modern Web Application and cacheability observations; retained,
not suppressed. Scanning covers the anonymous local shell, not all authenticated
or future QMS routes. Visual browser inspection confirmed the access screen.
The HTTPX identity smoke adapts Secure cookies only inside its loopback test
client; it does not validate real-browser identity flow or production TLS/MFA.

## Remaining release blockers from pinned third-party scans

| Image | Pinned digest | Scanner findings |
| --- | --- | --- |
| PostgreSQL 18 Alpine | `10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5` | 1 critical, 26 high, 33 medium, 25 low, 1 unknown |
| Keycloak 26.8.1 | `a78d6b79572168cb25886b80a8b5b8d4ed4390743e3eecb810538683e209dd6b` | 2 high, 55 medium, 35 low |
| SeaweedFS 4.51 | `f7a49e3f3972ebed5be2ed4befa4a0c68eb7bdddba6e692d42729ceb545134b8` | 1 unknown; no critical/high/medium/low |

Counts are scanner occurrences, not unique confirmed exploitable CVEs. PostgreSQL
findings include Alpine packages and Go standard library embedded in `gosu`.
Keycloak high findings concern packaged OpenJDK and have no fixed vendor version
listed in the observed report. Applicability and unknown findings need explicit
triage; lack of a patch or apparent reachability does not itself close a finding.
Do not bypass the new CI gate. Evaluate vendor fixes or tested hardened images,
with provenance, compatibility and regression evidence before release.

## Local operation and remaining product scope

UI: http://127.0.0.1:3000. Bound services use loopback; PostgreSQL has no host
port. Secrets are outside Git at `~/.config/pmcloud/dev.env`; do not paste them
into reports. The Colima `pmqms` VM uses 4 CPUs, 4 GiB and a 24 GiB requested disk.
It remains running for local development. Stop/start via
`./scripts/with-local-tools.sh colima stop pmqms` / `colima start pmqms`.
Tooling lives under ignored `artifacts/tooling/`; global Node is unchanged.

Evidence is under ignored `artifacts/`, including checkpoint, test, audit, scanner,
image and ZAP reports plus SBOMs. Local smoke data are fictional; no customer data
were used. Backup/restore, MFA enforcement, production deployment, full ASVS
mapping and all QMS domain modules remain pending. Document acceptance is defined
in `DOCUMENT_CONTROL_ACCEPTANCE.md`; no document/evidence module was implemented
by this hardening change.
