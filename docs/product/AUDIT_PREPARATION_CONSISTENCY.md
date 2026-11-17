# Audit preparation: concurrent changes and current access

Implemented 16 November 2026 (local); checkpoint timestamps use UTC17 November.
Base: PR57 / `8e31a588330bdeb9c8d82cc5d575af50b6c6e0c0`.

When an independence or competence assessment is withdrawn, its append-only
history advances without changing the audit planning version. Previously the
preparation response checked only the planning version. It could therefore return
a passed assessment already withdrawn during the request. It could also return
privileged diagnostic data after the reader lost the access used to calculate it.
The competence screen could still advertise an available review action after its
review grant was revoked during the read; its write command already revalidates.

## Implemented

- Preparation rechecks the active company/member context and scoped audit read
  access before returning. Expiring the parent avoids trusting its ORM cache.
- If review access was used to obtain execution-authority totals, its revocation
  rejects the response. The same applies to document read access used to assess
  documentary competence support. Denial is403/404, without a diagnostic payload.
- Preparation records the independence and, when readable, competence history
  versions. A new assessment or withdrawal observed by the final guard returns409
  and asks the caller to refresh. No assessment is edited or deleted.
- Competence recomputes its review eligibility after materialization. Losing only
  review access keeps authorized audit/document reading available, but returns
  `can_review=false` and the current reason.
- Response schemas, routes, no-store behavior, review segregation, capabilities,
  database policies and business transitions are unchanged. The existing web
  component handles409 with refresh and403/404 as access loss.

These are bounded point-in-time diagnostics under the existing transaction
isolation. This is **not** a serializable snapshot of every grant, document,
program and membership, nor a persisted execution authorization. A change after
the final guard can still occur. Future ready/start commands must atomically
revalidate their own preconditions. Historical assessments are not invalidated
merely because their author's review grant later changes.

`ready_for_execution` remains literally false. Audit execution, evidence,
findings, finding-to-NCR/CAPA, reports and closure remain pending.

## Verified

Six deterministic cases use separate real PostgreSQL runtime-role sessions;
Python hooks only place the concurrent transaction between the actual reads:

1. Audit read revoked after diagnostic materialization: access denied.
2. Review access revoked after authority totals: access denied.
3. Document read revoked after competence calculation: access denied.
4. Independence withdrawn during preparation:409; refresh shows withdrawn.
5. Competence withdrawn during preparation:409; refresh shows blocked.
6. Review access revoked during competence read: action unavailable with reason.

All six failed on the baseline and passed after the fix. Full internal-audit
integration: **127 passed** on final source, disposable schema0049, including
scope, criteria, team, agenda, independence, execution-authority and competence.
The populated-history destructive downgrade guard also passed. The six new cases
also passed on disposable schema0048, the local demo's version. No real database
was downgraded or migrated. One private harness attempt used an incorrect
PostgreSQL18 tmpfs path and was stopped; the corrected mount covers
`/var/lib/postgresql`. Only completed runs above count as accepted evidence.

API unit run:93 passed,568 database cases skipped without their separate
harnesses; those skips are not passing integration evidence. Existing framework
warnings concern Starlette/httpx and anyio aliases. Ruff and format:79 files;
mypy:43 source files; diff check passed. OpenGrep:6 rules on2 changed production
files,0 findings. Gitleaks worktree:0 findings. No dependencies changed. No new
browser, responsive, accessibility, visual-regression or frontend-build result is
claimed for this API-only increment.

## Local preview and recovery

Only `internal_audit_independence.py` and `internal_audit_competence.py` were copied
into a local API overlay, built without network or package installation. API
health passed; read-only rootfs, dropped capabilities and no-new-privileges remain
in place. Runtime otherwise remains PR39/schema0048 with the selective overlays
documented in CHECKPOINT.md, not the whole source branch.

24 real OIDC/API/web-proxy checks passed: both existing LAB-AUD records, operator
and reviewer, independence and competence, identity/version/scope and no-store;
foreign-company requests denied through both transports. No QMS business writes,
permission changes or schema changes. The first read-only QA attempt omitted the
required unit and exceeded the list limit; its422 was a harness error, corrected
before the accepted run. There were no fake approvals or new grants.

- Initial source/Git: `CP-AUDIT-READINESS-00-20261117T003532Z`,557 source entries.
- Before preview: `CP-AUDIT-READINESS-02-20261117T004122Z`,557 source entries.
- Both encrypted source restorations matched all SHA256 values; Git bundles
  verified. Backups and separate keys remain outside Git. The two previous runtime
  files were additionally encrypted and decrypt-byte-equality verified in CP02.
- Previous image: `pmcloud-api:before-audit-readiness-20261117`.
- Preview image: `pmcloud-api-audit-readiness:local`.

For a local API rollback, retag the preserved previous image as
`pmcloud-api:latest`, then recreate only `api` using the established local Compose
configuration and private development environment. No database restoration is
needed for this increment because it changes no QMS data or schema. No new DB or
S3 restoration test is claimed; earlier separately verified backups remain intact.

## Release status

Parent PR57 exact-head CI:quality43975076042 and CodeQL43975076095 passed;
security43975076032 failed only **Enforce final release gates**. Its scanner and
runtime steps succeeded, but that is not security approval for this new head.
Current vendor counts were not reverified here. New-head CI, independent code
review and human approval remain required. No merge or production deployment.
PM release decision remains **NO GO** pending the documented release blockers.

## CI follow-up

PR58/19fafd0 CodeQL43990314033 passed. Quality43990314141 passed its
integration/frontend/shell jobs but failed backend `mypy src tests`: two tests
accessed an imported alias through a module which does not re-export it. The
previous local mypy command checked only43 application modules, not the full79
application/test modules required by CI. Tests now reference the originating
competence function while still patching its caller boundary. No production
behavior, test assertion or CI gate was weakened; `mypy src tests` passes locally.
Security43990314009 failed only the final release gate. New-head CI remains
required. CP-AUDIT-CONTINUATION-00-20261117T010510Z verified encrypted source/Git
restoration before this correction.
