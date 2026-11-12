# Internal audit planning workspace

12 November2026 · `codex/internal-audit-planning-ui`, based on PR30/a7b2a9f.

## Implemented

- Separate Internal audits area, visible by explicit audits.* responsibilities;
  no implicit authority from owner/admin/auditor roles. Technical Audit trail remains separate.
- Programs: scoped search,20-record pages, objective/period/owner, create/edit,
  approve/activate/complete/cancel through existing versioned commands.
- Scheduled audits: independent unit-scoped pages, objective/type/dates,
  optional program and lead, scope summary, create/edit, mark planned/cancel.
  No global audit search or program-filtered count is invented.
- Paginated searchable reference choices preserve selected members/programs
  outside the loaded page. Dates render as UTC calendar dates.
- Read/manage/review gates mirror0040 API. Drafts survive503/422;409 locks stale
  submission and asks for explicit refresh.401/403/404 clear local records and
  permissions. Unknown success or network outcome locks repeat writes.
- Responsive light/dark tokens, keyboard tabs, skeletons, errors and empty states.
  Explicit accessible select names; selected tab contrast corrected after axe.
- Permissions UI exposes existing audit capability names; auditor-role eligibility
  includes audits.execute as permitted by0040. Execution screens remain unavailable.
- Development-only seed creates DEMO-AP-001 and DEMO-AUD-001 via realAPI,
  approved by reviewer and scheduled by manager. Independence remains pending.
  Repeat seed preserved one program/one audit. No new backend contract, dependency,
  business rule, migration file or production configuration.

## Recovery and local schema activation

Source/Git baseline CP-AUDIT-UI-00-20261112T214141Z restored416 source files.
Database backup CP-AUDIT-UI-DB-00-20261112T215516Z-r12 passed isolated restore
before applying existing0040.48 tables, every row/content digest, schema,
roles/credential fingerprints, sequences and unscoped runtime RLS were compared.
Encrypted dump/globals/inventory and verification helper stay outside the tree;
keys are separate0600. The public manifest contains no database rows or secrets.
Restore container used tmpfs, no network/ports and was removed by ownership label.
Source image was no longer available; hardened restore image used identical
postgres/pg_dump/pg_restore binaries verified by SHA256.

Raw DDL hashes initially differed because PostgreSQL reparsed constant varchar
array casts. Comparison normalizes only the two equivalent constant-array forms
and random dump guards, preserving all Boolean operators/grouping and otherDDL.
Built-in pg_* membership bootstrap grantor names are canonicalized; custom roles,
attributes and grants remain compared. Earlier failed recovery attempts were
retained and no schema change was made until r12 passed.

Local migration0039→0040 then succeeded explicitly.0041 was not copied or applied.
Only synthetic demo records and explicit demo-unit grants were added. The original
checkout's untested0041 WIP remains separate. Disk pressure was resolved by
regenerable build-cache cleanup, without removing data volumes or rollback images.

## Verification

- Existing0040 integrity plus9 new cases:11/11 disposablePostgreSQL PASS.
  Search literals, stable pages, cross-company/unit access and revocation covered;
  empty upgrade/downgrade and history downgrade guard PASS.
- Frontend lint/types/build and60 unit tests PASS.
- Browser full Linux regression:67/67PASS, no retries or snapshot updates.17new cases (16fixtures with intercepted writes plus1live read) and50existing regressions. Darwin17/17 final focused cases PASS.
- Earlier fixture failures were corrected for valid linked-program IDs, accessible select labels, scope-tab
  reset after refresh and explicit conflict refresh. A run overlapped a local web
  restart; it is not used as final evidence. No security protections were disabled.
- Live testing caught a missing same-origin proxy root; internal-audits is now explicitly allowed using the existing path validation and fixed upstream. No session/CSRF/authorization bypass. Reselecting the current unit no longer clears access without reloading.
- Gitleaks and license policy PASS; no new dependencies. FullCI of the newhead
  remains required. PR30/a7b2a9f CI was quality/CodeQL/runtime/50browser PASS,
  release FAIL only Keycloak7High/SeaweedFS2High; this does not approve this branch.

## Limits

This delivers0040 planning UI, not complete internal auditing. Structured scope,
criteria, agenda/team, independence decisions, execution/evidence, findings,
NCR handoff and Action Center remain pending. Program completion does not close
linked audits; cancelled program relations can block later edits until explicitly
replaced or cleared. No claim of ISO certification or production approval.

Main is not updated automatically. Integration remains a draft PR with human
review before merge, and no production deployment.


The existing overview visual baseline retains its original collaborator
responsibility fixture (without audit grants), rather than changing old golden
images to accept a different persona. New authorized audit navigation and both
themes have separate coverage. No golden PNG was updated.


Final source/Git recovery checkpoint: **CP-AUDIT-UI-06-20261112T222230Z**. Public manifest in `.ai/checkpoints/`; encrypted artifacts and separate keys remain outside Git. CI of the delivery head remains required; independent final code review and human approval are still required before merge.
