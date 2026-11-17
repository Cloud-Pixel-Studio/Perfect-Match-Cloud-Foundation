# Printable audit planning copy

Delivered scope: read-only HTML download from the existing internal-audit detail.
Open Internal audits, select an authorized unit, choose Scheduled audits and an
audit, then **Download audit plan**. Open the downloaded HTML to print or use the
browser's Save as PDF. No automatic PDF generation is claimed.

## Behavior and boundaries

The copy contains the selected company and unit, audit identity/state/planning
version, objective, scope, criteria, planned team and UTC agenda. Withdrawn items
remain visible with their reasons. Empty sections are explicit. Lead names come
from the planned active auditor roster, not an unrestricted directory lookup.
Assessment rationale, competence documents, conclusions, execution results and
technical logs are excluded. It is labelled **Planning copy**, never an issued
report, readiness approval or certificate.

Existing `audits.read` access is sufficient; no manage/review grant is required.
All reads use the existing authenticated same-origin proxy and API. No business
write, new route, API contract, capability, schema or backend change is introduced.
The team endpoint is the existing `/team-members`, not `/team`.

Every page is fetched in batches of50 and validated against the selected audit
and unit; duplicate IDs, missing linked scope/team references and malformed rows
reject the entire export. Maximum500 items per section; larger plans fail with
an explicit message rather than silently truncating. Parent version/content and
user/company context are reread before creating the file. Revoked read access,
changed context or changed planning prevents a partial download. These are
bounded optimistic checks, not a serializable snapshot or reusable permission.
Existing DB rules advance the parent when its planning children change.

Collection is cancellable and aborts on unmount/version change. Controls use the
existing design tokens, disable conflicting editors, announce loading/success/
error and handle access loss through the existing workspace callback. The output
escapes all record text, uses a restrictive CSP, contains no scripts/forms/remote
resources, and downloads with a sanitized versioned filename. Customer content is
not uploaded, persisted in localStorage or committed to Git.

## Verification

-19 new unit cases; total83 frontend tests/17 files PASS after the final production
  source change. Covers pagination beyond the visible register, withdrawals,
  empty sections, HTML injection/filename safety, cross-unit rows, duplicate/large
  pages,500-item boundary, missing references, changed version/company/user,
  access revocation and abort. Test transport asserts GET/default method,
  credentials included and no-store.
- Frontend lint, full typecheck including E2E sources, and production build PASS.
- Two durable Playwright scenarios added: read-only-profile fixture download and
  real synthetic API/proxy download, with responsive captures and axe checks of
  the generated HTML. They were **not run locally**; new-head CI must execute them.
  No pixel-baseline comparison or full WCAG conformity is claimed.
- Real browser/OIDC download PASS for LAB-AUD-002, plan version5. The actual file
  contains all four sections and current scoped planning; no QMS data/grants/schema
  writes. The first browser attempt revealed the wrong team endpoint; corrected
  and reverified before delivery. A static parser rejected script/frame/form/
  image/object/embed tags and inline event handlers in the actual output.
- Document inspected at1280px and in a real375px iframe viewport:0 horizontal
  overflow; mobile CSS computes margin0/padding24px20px. Browser viewport capability
  failed, so the375px check used this isolated document frame instead. UI light/
  dark inspected, screenshot saved, initial light theme restored. Five static
  text/background pairs meet AA:14.02,6.01,5.05,6.93,7.54. This is scoped contrast
  evidence, not a full accessibility audit.
- Local captures and actual HTML: `artifacts/previews/2026-11-17/` (ignored by Git).
  Includes audit-plan-before/after/after-dark.png, document-desktop/mobile.png and
  audit-plan-LAB-AUD-002-v5.html. Backup evidence is sealed separately outside Git.
- Post-preview regression:24 real OIDC/API/web-proxy reads PASS, including foreign-company denial;0 QMS writes/grant/schema changes.
- Dependency license policy PASS (56 Python/13 direct Node entries). Gitleaks working tree:0 findings. No new UI library or licensed standards text.

## Framework security patch

Next16.4.3's build reported GHSA-mfr8-8qww-v76h (Moderate), confirmed against the
[vendor advisory](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h).
Next and eslint-config-next are pinned to16.4.5; lockfile changes are restricted
to the Next family. The vulnerable `use cache`/`unstable_cache` combination was
not found in application sources; absence is not a universal exploitability proof.
The advisory is absent from the post-update package audit:1 remaining Moderate
(minimatch, development chain),0 High/Critical. No scanner exclusion or release
gate was weakened. Vendor-image findings remain separate and unresolved.

## Preview and recovery

The actual local API remains0048 plus the existing selective fixes. To avoid
activating unsupported A02 frontend against that API, the preview was built from
verified PR39/f856254 frontend with ONLY the export files and patched Next
manifest/lock/dependencies. Full current-branch build passed separately.
The isolated source/dependency copy did not overwrite any checkout or prior WIP.

Local web image `pmcloud-web-audit-export:local` replaces only derived application
files in a new image, built without network/package installation; previous image
`pmcloud-web:before-audit-plan-export-20261117` is retained. Actual Node runtime
reports Next16.4.5. Health, read-only rootfs, cap_drop ALL and no-new-privileges
PASS. A first version probe used the wrong package working directory; the corrected
`/app/apps/web` probe passed. This preview is not a fresh vendor/container scan.

CP-AUDIT-EXPORT-00-20261117T010817Z verified559 source files plus Git before edits;
CP-AUDIT-EXPORT-02-20261117T012025Z verified562 before dependency updates. Encrypted
source restoration/hash and Git bundle verification PASS; backups and keys remain
outside Git. No DB migration or business mutation; no new DB/S3 restore claimed.
For rollback, retag the preserved previous web image to pmcloud-web:latest and
recreate only web with the established local Compose/environment. No data reset.

PR58's mypy follow-up8a24809 now has quality43993188442 and CodeQL43993188323 PASS;
security43993188444 failed only Enforce final release gates. This does not certify
the export branch. New-head CI, independent review and human approval are required.
No merge or production deployment. Ready/start, execution, findings, issued reports
and audit closure remain pending; PM release decision remains NO GO.
