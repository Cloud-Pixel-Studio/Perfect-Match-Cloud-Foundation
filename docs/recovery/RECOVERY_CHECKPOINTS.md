# Recovery checkpoints

External encrypted checkpoints are stored under the local PerfectMatchQMS recovery
directory, never in Git. Their encryption keys live separately under the protected
pmcloud configuration directory.

| Checkpoint | Purpose | Recovery status |
| --- | --- | --- |
| `CP-00-20261102T125420Z` | Initial baseline before audit | Source listed, Git bundle verified, DB restored |
| `CP-01-20261102T130500Z` | Architecture/security/UI audit | Manifest recorded; source unchanged from CP-00 |
| `CP-02-20261102T131000Z` | Before agent configuration | Byte-identical encrypted CP-00 recovery artifacts verified |
| `CP-03-20261102T132000Z` | Agent policies/configuration | Source/Git verified; DB restored successfully |
| `CP-04-20261102T133000Z` | Focused security hardening | Source/Git verified; DB restored successfully |
| `CP-04-20261102T150500Z` | Post-hardening runtime at 0039 | Source/Git verified; DB restored successfully |
| `CP-05-20261102T151100Z` | Visual system and screenshot baselines | Source/Git/visuals verified; DB restored successfully |
| `CP-05-20261103T172255Z` | Premium product catalog and workspace milestone | Source/Git/6 Darwin visuals verified; DB restored successfully |
| `CP-05-20261104T003517Z` | Premium operational-module visual milestone | Source/Git/18 visual PNGs verified; DB restored successfully |
| `CP-BRAND-00-20261104T015019Z` | Branding work initial baseline | Source/Git/local diff encrypted; decryption and bundle verified |
| `CP-BRAND-06-20261104T020606Z` | Aligned Evidence pre-integration boundary | Source/Git/diff/DB encrypted; isolated DB restore passed on 0039 and 48 tables |
| `CP-VISUAL-00-20261109T182914Z` | Before visual completion work | Source and complete Git bundle encrypted; decryption, archive listing and bundle verification passed |
| `CP-VISUAL-05-20261110T214408Z` | Persona navigation, workflow dialog and audit workspace | 565-entry source and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-06-20261110T215335Z` | Post-review visual/security integration boundary | 565-entry source and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-07-20261110T221055Z` | Reviewed Linux visual baseline correction | 346 tracked-source entries and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-08-20261110T222519Z` | Deterministic pinned Linux visual runtime | 347 tracked-source entries and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-09-20261111T022612Z` | Stable authenticated visual fixture and serialized CI | 347 tracked-source entries and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-10-20261111T023554Z` | Visual artifact ownership handoff | 347 tracked-source entries and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-VISUAL-11-20261111T025137Z` | Deterministic authenticated-session readiness | Tracked source and complete Git bundle encrypted; stream decryption, archive listing and bundle verification passed |
| `CP-AUDIT-00-20261111T030311Z` | Internal-audit initial baseline | 348-entry source, complete Git bundle and database encrypted; isolated restore passed on 0039 and 48 tables |
| `CP-AUDIT-01-20261111T125152Z` | Internal-audit planning slice before commit | 353-entry source and Git bundle encrypted/verified; unchanged 0039 database baseline re-encrypted and matched to CP-AUDIT-00 |
| `CP-AUDIT-02-20261111T133146Z` | Internal-audit planning slice with CI gate | 353-entry source and Git bundle encrypted/verified; unchanged 0039 database baseline digest matched and catalog read passed |
| `CP-DESIGN-STUDIO-01-20261111T181713Z` | AI Design Studio visual foundation | 373-entry source and complete Git bundle encrypted; archive listing and bundle verification passed; database unchanged |
| `CP-DESIGN-STUDIO-02-20261111T182451Z` | Verified AI Design Studio pre-commit boundary | 378-entry source and complete Git bundle encrypted; archive listing and bundle verification passed; database unchanged |
| `CP-DESIGN-STUDIO-03-20261111T183407Z` | Final Design Studio pre-integration boundary | Includes reviewed Darwin/Linux baselines and supersedes CP-DESIGN-STUDIO-02; encrypted hashes and restoration evidence recorded below |
| `CP-DESIGN-STUDIO-04-20261112T014909Z` | Before visual polish and cross-chat handoff | Encrypted source archive listed and complete Git bundle verified; separate key mode0600; database unchanged |
| `CP-DESIGN-STUDIO-05-20261112T023324Z` | Final visual polish and cross-chat handoff | 385-entry encrypted source listed, complete Git bundle verified, separate key0600;43 unit tests and final Linux16/16 repeated without snapshot updates |
| `CP-06-20261102T202506Z` | Final pre-GitHub integration state | Source/Git/visuals verified; DB restored successfully |
| `CP-06-20261102T204905Z` | Authorized integration boundary | Source/Git/visuals verified; DB restored successfully |
| `CP-06-20261103T032216Z` | Post-PR CI and recovery verification | Source/Git/12 visuals verified; DB restored successfully |

CP-00 database restoration produced Alembic `0038_capa_document_links`, 46 public
tables and 25 CAPA rows in an isolated disposable PostgreSQL container. The restore
container was removed after verification.

CP-04 restoration independently reproduced Alembic `0038_capa_document_links`,
46 public tables and 25 CAPA rows. Its source archive listed 597 entries and its
Git bundle contained complete history with 13 refs. This checkpoint includes the
focused JOSE dependency remediation and the verified test state; it does not
claim that the release gate passes.

The later CP-04 instance supersedes the earlier one as the current security-phase
recovery point. Its isolated restore reproduced Alembic `0039_capa_trace_links`,
48 public tables, 28 CAPA rows and one active direct control link. The earlier
CP-04 remains available as a verified pre-migration rollback point at 0038.

CP-05 independently restored Alembic `0039_capa_trace_links`, 48 public tables,
28 CAPA rows and one direct control link. Its separate visual archive contains six
PNG baselines covering the public catalog and authenticated workspace across
mobile, tablet, desktop and dark-theme states.

CP-05 `20261103T172255Z` preserves the updated premium product catalog and
authenticated workspace presentation. Its encrypted source, complete Git bundle
and six reviewed Darwin baselines were decrypted and listed; the database was
restored into an isolated PostgreSQL container at Alembic 0039 with 48 public
tables and 28 CAPA rows. Seven local Playwright/axe scenarios pass. Linux
baselines and broader human UX acceptance remain pending, so this checkpoint is
a recovery point rather than release approval.

CP-05 `20261104T003517Z` extends that recovery boundary through processes,
documents, controls, risks, NCR and CAPA. Its encrypted source lists 301 entries,
the complete Git bundle verifies, and 18 baseline/audit PNG files decrypt and
list correctly. The database restore was independently verified at Alembic 0039,
48 public tables and 28 CAPA rows. Nine local Playwright/axe scenarios pass;
fresh Linux runtime and human acceptance remain pending.

CP-VISUAL-05 `20261110T214408Z` preserves the verified local visual-completion
tree before Git integration. It includes the persona-aware navigation, native
workflow editor dialog, audit evidence workspace, Darwin workspace baselines and
the read-only active-capability summary. It does not include environment files,
runtime artifacts or database content; no schema or customer data changed. The
key remains separate with mode 0600.

CP-VISUAL-06 `20261110T215335Z` supersedes CP-VISUAL-05 as the pre-Git boundary.
It also preserves the independent-review correction that couples evidence-review
actions to the control context required to open and complete them, and requires
the explicit `evidence.review` capability at the review endpoint. It contains no
database or environment material; its separate key has mode 0600.

CP-VISUAL-07 `20261110T221055Z` preserves the two reviewed Linux workspace
baselines regenerated after PR #15 correctly rejected their stale predecessors.
The official Playwright 1.64.1 Linux container passes all 13 scenarios against
these files. The encrypted archive is restricted to Git-tracked source, and its
complete Git bundle verifies; no database, environment value or customer data is
included. Its separate key has mode 0600.

CP-VISUAL-08 `20261110T222519Z` supersedes CP-VISUAL-07 for visual CI
reproducibility. CI demonstrated that all six screenshot comparisons drifted on
the mutable GitHub runner even when four untouched product baselines were used.
The regression now runs in the official Playwright 1.64.1 Noble image pinned by
manifest digest and receives only synthetic test credentials. ShellCheck,
workflow YAML parsing, license policy and all 13 scenarios pass locally in that
exact runtime. The encrypted tracked-source archive and complete Git bundle were
verified; no database, environment value or customer data is included.

CP-VISUAL-09 `20261111T022612Z` adds deterministic authenticated screenshot
content and serializes CI browser workers after the pinned runtime proved that
the remaining variation came from database-specific action counts and concurrent
owner/member logins. Only the two screenshot scenarios use the fixed compact
action fixture; real-API deep-link and exact-record tests remain unchanged.
Darwin and Linux mobile baselines were reviewed, and Linux lint, typecheck and
all 13 Playwright/axe scenarios pass. Source and Git recovery artifacts were
encrypted and verified with a separate mode-0600 key.

CP-VISUAL-10 `20261111T023554Z` preserves the ownership handoff added after the
official PR run passed the pinned Linux visual/axe gate but exposed root-owned
Playwright reports blocking the later ZAP step. The container now restores those
files to the runner UID/GID while preserving Playwright's exit status. ShellCheck
and all 13 scenarios pass locally, and report/result ownership was verified.
Source and Git recovery artifacts were encrypted and verified with a separate
mode-0600 key.

CP-VISUAL-11 `20261111T025137Z` preserves the authenticated browser-test
readiness correction after the next PR run exposed a real OIDC callback race.
The shared helper now waits for the final web redirect, a successful `/auth/me`
response and the initial workspace before following a requested deep link.
ESLint, TypeScript and two consecutive runs of all 13 scenarios pass without
retries in the pinned Linux image. The encrypted tracked-source archive and
complete Git bundle were verified; no database, environment value or customer
data is included, and the separate key has mode 0600.

CP-AUDIT-00 `20261111T030311Z` is the clean baseline before internal-audit
schema work. Its encrypted source lists 348 entries, the complete Git bundle
verifies, and the encrypted PostgreSQL dump restores independently at Alembic
`0039_capa_trace_links` with 48 public tables. The separate key has mode 0600;
no environment file or plaintext database dump is stored in the repository.

CP-AUDIT-01 `20261111T125152Z` preserves the verified first internal-audit
vertical before commit:
programs, audit planning, four explicit scoped capabilities, forced RLS,
controlled transitions, immutable technical events and its disposable database
test harness. The unchanged live database snapshot is re-encrypted from the
restored CP-AUDIT-00 baseline and its decrypted digest must match. The source,
complete Git bundle and database remain outside the working tree with a separate
mode-0600 key. The final timestamp and verification counts are recorded after
checkpoint creation.
The source, Git bundle and database ciphertext SHA-256 values are respectively
`16f9344a0c2600eb2b1dfad5381374688ae197a23dcb501d30e22e738f432067`,
`97153b50462eba07f81c4f54c29b8a06ba4b2401fa1f0e51ebecea1b91318ee2`
and `b31649c11b6d516c3c8af446c02c6ffb73cd43fe522faa646f73374c40c8b1fe`.

CP-AUDIT-02 `20261111T133146Z` supersedes CP-AUDIT-01 as the verified
pre-commit boundary. It adds the independent `internal-audit-integrity` quality
job, includes the suite in `scripts/checkpoint.sh`, validates the expected
downgrade failure reason without noisy traceback output, and preserves the
Ruff/mypy corrections required by the exact CI commands. Its encrypted source,
Git bundle and unchanged database snapshot hashes are respectively
`8c8cba07f7e71419f994333ba43bdc61f033e4999ca3a3f8854cfa36d57d36fd`,
`6a734e9dceaf1c9a37f4b4ab72fcb4e6da67e61bea66638389059a854566eb5a`
and `f55561250188cea898cad8f2f2dc8bde767ed8c8e4c331bc2964ed101785ecb6`.
The separate key is mode 0600; the decrypted database digest matches the
restored CP-AUDIT-00 baseline and `pg_restore` reads its catalog.

CP-DESIGN-STUDIO-01 `20261111T181713Z` preserves the isolated Design Studio
implementation before commit. Its source archive includes the Brand Kit, five
agent contracts, two generated source visuals, one synthetic product capture,
six deterministic PNG exports, gallery, renderer, policies, tests and documents.
The encrypted source and Git bundle hashes are respectively
`6588ea9b61138c20a12c1b29b7377a2ac75535d7bb373d63f4b824c755497397`
and `f4873b571711d886710c81d6d1ee282e1134003e770ebea1b1d319a0db105d98`.
Both recovery checks passed; the key is separate with mode 0600. No database,
environment file, provider credential or customer data is included.

CP-DESIGN-STUDIO-02 `20261111T182451Z` supersedes CP-DESIGN-STUDIO-01 as the
verified pre-commit boundary. It adds the six exact PNG exports, asset/hash and
dimension tests, responsive Playwright/axe baselines, CSP-safe logo rendering,
tool evaluation and implementation report. The encrypted source and Git bundle
hashes are respectively
`00e4fba1f11642cf57821524de0917a8bb8d0c43071edaaa6337519ac9505625`
and `53a1c2a3853239e4abc8b4f2632cab5f7f32c0cdd05cbd0c2887a16921cf9f8d`.
Both recovery checks passed; the key is separate with mode 0600. The database,
runtime services and production remain unchanged.

CP-DESIGN-STUDIO-03 `20261111T183407Z` supersedes CP-DESIGN-STUDIO-02 before
GitHub integration. Its additional evidence is the independently rendered and visually
inspected Linux mobile/desktop baseline pair, followed by a second unchanged
2/2 Playwright/axe run in the official image pinned by digest. It preserves 380
source entries and a complete Git bundle. The encrypted source and Git bundle
hashes are respectively
`4f3f5cca66b9f3dd8e32678c89d5b700c1fc465df87b192eb1139c55be52baf2`
and `0b58532309cb1e5e74341240890a5cde62f35d3b48a16e920ad0b0091e7f9541`.
Archive listing and Git bundle verification passed; the separate key is mode
0600. Database, runtime services and production remain unchanged.

CP-06 preserves the remediated independent-review state: fresh Keycloak evidence,
deferred fail-closed CI image gates, SHA-pinned CodeQL, controlled agent intake and
185 passing process-integrity tests. Its isolated restore reproduces Alembic
`0039_capa_trace_links`, 48 public tables, 28 CAPA rows and one active direct
control link. The release gate remains FAIL; CP-06 is a recovery and review point,
not approval to publish, merge or deploy.

The later CP-06 instance adds only the recorded authorization to commit, push the
dedicated branch and open a Pull Request. It is the recovery point immediately
before those GitHub actions. Merge and deployment remain outside that authorization.

CP-06 `20261103T032216Z` preserves PR #13 at `8930aa6` after official CI. Its
isolated restore reproduces Alembic `0039_capa_trace_links`, 48 public tables,
28 CAPA rows and one active direct control link. The Git bundle verifies complete
history with 19 refs; the visual archive contains twelve Darwin/Linux baselines.
Quality, CodeQL, runtime, six Playwright/axe regressions, five SBOMs and ZAP pass.
The release gate intentionally remains FAIL because pinned Keycloak and SeaweedFS
images retain five and one High findings respectively.

This document contains identifiers and outcomes only. It intentionally excludes
keys, secrets, environment values, database content and customer data.

CP-DESIGN-STUDIO-04 preserves remote-synchronized commit `4ad33be` before
the logo, theme and download follow-up. The encrypted source and bundle SHA-256
are `5efa97a05eada1c2e44ff81d2b62628660624aaaf2153c776b85f3c522b1d68c`
and `8864024bbb059db6077b51ec3ce790f6f50ae58235c0d20c1e4db9930202f72e`.
Source listing and bundle verification passed; no database mutation is part of
the visual change. The date suffix is UTC (11 November in America/New_York).

CP-DESIGN-STUDIO-05 preserves the final visual follow-up and cross-chat guide
before integration. Its encrypted source and bundle SHA-256 are
`54285f2fc8f22d02929d19cef89f28f4de4ff879fce7275195c6c019ebd1781d`
and `825d4ba26b51766dc7532c8e06ed3668226e91798edefc87818d3b4d3165040b`.
The archive contains385 entries; stream decryption/listing and bundle verification
passed. The key is stored separately with mode0600. No database, customer data
or environment file was included. The snapshot is based on4ad33be and includes
the uncommitted visual delta; the audit0041 draft remains in its separate branch.


CP-MARKETING-00 `20261112T024646Z` preserves91b26b5 before the public-product
marketing change. Source768 entries and complete Git bundle are encrypted outside
the worktree; stream decryption/listing and bundle verification passed again on
12 November. Cipher hashes are
`dd6dea0483b9c9bfea64e9ebb6b8bfba2b541653c9ae373fc0e451367868d60f`
and `0bcd20a3f0e61230ef308d5d3744123b5923942b061c49633566ebc6c4771f67`.
No environment file, database or customer data was included.

CP-MARKETING-06 `20261112T140941Z` is the preintegration boundary for the
product tour, synthetic UI captures, contact/brief flow, visual references and
external-branch reconciliation. Encrypted source and Git history, per-file
hashes and restoration verification live in protected external storage with
a separate0600 key. No schema/data mutation: no new DB restore claimed.
The final verification includes59 unit tests, lint/types/build, Darwin19 and
Linux19 repeated without snapshot updates/retries; release remains blocked.
