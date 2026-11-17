# Structured internal-audit scope · 12 November 2026

## Delivered boundary

An audit now has ordered, descriptive scope items with an optional link to an
active process in its own company and unit. Authorized planners can add, edit
or withdraw an item with a reason; withdrawal preserves its history. Active
orders are unique within each audit. Active and withdrawn lists are paginated.

This extends planning, not audit execution. Criteria, agenda/team, independence
review, readiness, evidence, findings and finding-to-NCR handoff remain pending.
The lead-auditor field and pending independence flag do not establish independence.
No commercial, licensing, authentication or Odoo dependency changes were made.

## Architecture and contract

- Migration `0042_internal_audit_scope` follows `0040_internal_audit_foundation`.
  Revision0041 is deliberately reserved for the preserved, unvalidated draft in
  the original checkout/recovery branch; it is not part of this migration chain.
  That draft calls one PostgreSQL trigger function from another as an ordinary
  function. This delivery instead uses one real trigger and does not modify or
  apply the draft. Never combine the two Alembic histories automatically.
- `qms_audit_scopes` has forced RLS and composite company/unit foreign keys to
  its audit and optional process. Runtime has no DELETE/TRUNCATE permission.
- Read requires `audits.read`; writes also require `audits.manage`. Choosing or
  retaining a process during editing requires `processes.read`. Retirement can
  preserve an old process link even when that process is inactive/unreadable.
- Writes lock the parent and require both the expected audit version and, for
  existing items, expected scope version. SQL advances the parent version even
  for a direct runtime SQL write. Only draft/planned audits accept changes.
- Each API operation appends `internal_audit.updated` under the parent audit ID,
  including scope ID/order/version/status/process and hashes of narrative fields.
  The scope change, parent version and technical event commit atomically.
- Withdrawn items cannot be edited/reinstated or have content changed as part
  of retirement. The API offers no delete command. A migration downgrade refuses
  to remove scope rows or recorded scope-event history.

Routes beneath `/internal-audits/audits/{audit_id}`:

| Method/path | Behavior |
| --- | --- |
| GET `/scopes` | Optional active/withdrawn status, limit1–50, bounded offset |
| POST `/scopes` | Create using expected_audit_version; returns201 |
| PATCH `/scopes/{scope_id}` | Edit using expected parent and scope versions |
| POST `/scopes/{scope_id}/withdraw` | Reasoned withdrawal using both versions |

Writes return `{scope, audit_version}`. Existing identity/CSRF and same-origin
proxy checks remain enforced. Cross-company/unit, unknown and inaccessible
records are hidden; version and planning-state conflicts return409.

## UI behavior

Internal audits → Scheduled audits → select audit → Structured audit scope.
The editor uses existing enterprise tokens/components and both themes. The
optional process selector searches and paginates its real scoped API; selection
survives a page/search change. Lack of process-read responsibility does not
expose the process directory.

A409 locks submission until explicit refresh. Refresh retrieves the full parent
state as well as its version: a concurrently cancelled audit loses edit controls.
Network failure or an unconfirmed2xx also blocks blind replay. An explicit503
preserves the draft without an automatic retry.401/403/404 clears the cached
planning context. Stale/unmounted reads and writes cannot repopulate another
unit. Response IDs/unit/version/status are validated before accepting a result.

## Local recovery and demo

Source/Git baseline: `CP-AUDIT-SCOPE-00-20261112T230734Z`,422 entries restored by
SHA256 and Git bundle verified. The dedicated branch is `codex/internal-audit-scope`,
based on PR31/5f25342. Original checkout changes and unvalidated0041 are preserved.

Before any local schema mutation, separate encrypted recovery checkpoint
`CP-AUDIT-SCOPE-DB-00-20261112T231842Z` restored0040 into a network-isolated,
portless, tmpfs PostgreSQL container. All50 table contents, schema/owners/ACLs,
roles/credential fingerprints, sequences and44 forced-RLS tables matched.
Source image was unavailable; SHA256 of postgres/pg_dump/pg_restore executables
matched the hardened fallback image. Only equivalent constant-array deparser
casts and built-in pg_* bootstrap grantor names were normalized; custom grants
and table contents were compared without relaxation. Ciphertexts, HMACs,
inventory and verification helper are outside Git; keys are separate0600.

Local preview migrated explicitly0040→0042 after this recovery PASS. The seed
uses real API commands to add one synthetic scope to DEMO-AUD-001, linking the
active DEMO-PROC-001. It checks all scope-history pages first, including withdrawn
items, and does not resurrect a withdrawn demo. Two seed runs succeeded. No
customer records or existing scope wording were overwritten. Rollback images
`pmcloud-api:before-audit-scope-20261112` and web equivalent remain available;
image rollback alone does not undo database history. Never downgrade a populated
audit database: use reviewed forward fixes or restore the isolated backup first.

## Verification and remaining review

- Dedicated disposable PostgreSQL suite:20/20 PASS (11 existing+9 scope cases),
  including cross-company/unit denial, revocation, process responsibility,
  parent/scope optimistic versions, duplicate-order atomicity, immutable history,
  direct SQL restrictions and upgrade/downgrade guards.
- Ruff format/lint and mypy60 source/test files PASS. Default API unit suite:
  50 PASS,317 integration tests skipped without their individual DB harnesses;
  the20 audit integrations above were executed separately, not counted as skipped.
- Frontend lint/typecheck/build and60 unit tests PASS. Ten new Linux browser
  scenarios PASS, all writes intercepted; real seed/API persistence and a live
  browser read are separate evidence. Full Linux regression77/77 PASS; Darwin10/10 PASS. Final targeted Linux
  repetition after the pagination-button polish is recorded in CHECKPOINT.md. No golden images are updated to accept changes.
- Gitleaks tree/history, license policy and ShellCheck PASS. Six Python OpenGrep
  rules over four changed application files:0 findings; not a full security audit
  or TypeScript scan. No dependency added; production dependency audit0 findings; all-dependency audit1 pre-existing
  Moderate and0 High/Critical.
- Known two API deprecation warnings predate this change. A mistakenly broad
  standalone Ruff invocation found existing long demo literals; new strings
  were split and unrelated seed formatting was restored. API quality passes.
- Independent final review and CI of the exact delivery head remain required.
  PR31/5f25342 quality43319632987 and CodeQL43319632754 passed; security43319632849
  failed only its final release gate. That evidence does not approve this branch.
  No production deployment, merge, ISO certification or security-readiness claim.

Post-migration database recovery: **CP-AUDIT-SCOPE-DB-06-20261112T233026Z**, isolated restoration PASS
in0042 with51 tables/45 forcedRLS tables, including demo scope. Final source/Git
checkpoint: **CP-AUDIT-SCOPE-06-20261112T233207Z**; see the public manifests for verification status.

Entrega: [PR borrador32](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/32), sobre PR31. Commit funcional `072e309484b78144cf811bc228ab292361382bbc`, árbol `c0a934d0af58e38e8c7dba96f94004b145a80ca4` idéntico local/remoto. Este seguimiento solo documenta continuidad. CI del nuevo head pendiente, revisión independiente y aprobación humana antes de merge; sin producción.
