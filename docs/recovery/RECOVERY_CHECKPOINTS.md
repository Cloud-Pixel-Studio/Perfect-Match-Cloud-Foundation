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
