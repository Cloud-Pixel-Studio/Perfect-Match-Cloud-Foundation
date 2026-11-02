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
| `CP-06-20261102T202506Z` | Final pre-GitHub integration state | Source/Git/visuals verified; DB restored successfully |
| `CP-06-20261102T204905Z` | Authorized integration boundary | Source/Git/visuals verified; DB restored successfully |

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

CP-06 preserves the remediated independent-review state: fresh Keycloak evidence,
deferred fail-closed CI image gates, SHA-pinned CodeQL, controlled agent intake and
185 passing process-integrity tests. Its isolated restore reproduces Alembic
`0039_capa_trace_links`, 48 public tables, 28 CAPA rows and one active direct
control link. The release gate remains FAIL; CP-06 is a recovery and review point,
not approval to publish, merge or deploy.

The later CP-06 instance adds only the recorded authorization to commit, push the
dedicated branch and open a Pull Request. It is the recovery point immediately
before those GitHub actions. Merge and deployment remain outside that authorization.

This document contains identifiers and outcomes only. It intentionally excludes
keys, secrets, environment values, database content and customer data.
