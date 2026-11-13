# Audit agenda ·13November2026 UTC

## Implemented boundary

Migration0045 follows0044 (0041 remains a reserved, unvalidated recovery draft).
Audit planners can create, edit and retire agenda activities, assign an active
planned auditor, optionally select an audited participant and active scope,
and record method, objective, location, sequence and a UTC interval.
This is planning only: no execution authority, invitations, qualification or
independence approval is granted. Readiness must later revalidate active company
membership, access, competence and independence; an assignment is not proof.

## API and database contract

Under `/internal-audits/audits/{audit_id}`:

| Method/path | Behavior |
| --- | --- |
| GET `/agenda` | Bounded limit1–50/offset; optional active/withdrawn status |
| POST `/agenda` | Create with expected parent version |
| PATCH `/agenda/{agenda_id}` | Edit with expected parent and item versions |
| POST `/agenda/{agenda_id}/withdraw` | Reasoned retirement with both versions |

Writes return `{item, audit_version}`. Reads include recorded auditor/auditee
names from the immutable planning-team snapshots, using one batch query.
The team list accepts an additive `team_role=auditor|auditee` filter for pickers.
CSRF/session/proxy defenses and company/unit authorization remain in force.

`qms_audit_agenda_items` has forced RLS, exact composite company/unit/audit
references to scope and team, no runtime DELETE/TRUNCATE, bounded sequence,
active-order uniqueness, immutable identity and terminal withdrawn records.
Read requires audits.read; mutations also require audits.manage. Company roles
and commercial seats do not imply those capabilities.

Parent lock and expected versions serialize API writes. SQL independently checks
active participant roles/scope, planning state, UTC minute precision, positive
intervals and the parent date window. End may equal midnight immediately after
the last planned date. Overlap for the same auditor OR same audited participant
is rejected **within this audit**. Adjacent activities and activities with different
participants may run in parallel. There is no cross-audit/company calendar or
global double-booking guarantee. Parent locking was tested with two concurrent
runtime SQL sessions: one commit and one rejected overlap, with one parent bump.

Active linked agenda protects a team role/retirement, scope retirement and
shrinking parent dates. Reassign or retire the linked activities first; note-only
team edits remain possible. Retirement never rewrites activity content. SQL
triggers also protect direct runtime writes; API writes additionally append an
atomic internal_audit.updated event. Narrative fields enter the event as hashes,
not raw objective/title/location/reason. Downgrade refuses rows or agenda event
history; empty upgrade/downgrade/re-upgrade was tested only in disposable DBs.

## UX, accessibility and demo

Scheduled audits → select audit → Audit agenda. There are active/history views,
bounded pagination, accessible create/edit/withdraw forms and explicit UTC labels.
Auditor/auditee pickers use role-filtered, paginated real team records; scope is
optional and paginated. Selection stays pinned across pages. UTC is intentional;
company timezone preferences and external calendars remain future work. Retired
activities retain their original interval even after the parent dates change;
history is not validated against the new active window. Planning detail still
stacks scope, criteria, team and agenda sections; reducing that vertical scroll
with section navigation is a subsequent UX improvement, not implemented here.

Loading/error/empty/success states and light/dark responsive styles reuse the
existing design system. Epoch/abort guards reject stale scope results. Permission
loss clears cached planning context;409 forces explicit parent reconciliation;
503 preserves a draft; network/unconfirmed/mismatched success blocks blind replay.
Server confirmation must match submitted identity links, sequence/title/method
and timestamp instants. Refresh obtains the complete parent, including state.

Development seed, through the real API, adds one synthetic activity named
“Revisión de recepción — demostración”, linked to the synthetic scope/auditor,
09:00–10:00 UTC. It pages existing records, chooses an unused order and does not
resurrect a retired demo activity, overwrite work or grant permissions. Two seed
runs and readback verified exactly one active activity and the preceding demo
program/audit/scope/criterion/team. Existing production-environment refusal stays
in force. Live browser reading is separate from mocked command tests.

## Verification

- Real PostgreSQL:58/58 audit integrations (15 agenda tests), including concurrent
  SQL overlap, RLS/authority/IDOR, stale versions, UTC bounds, active references,
  retirement guards, parent dates, atomic events and bounded reads. Empty migration
  roundtrip and history-protected downgrade PASS.
- Existing process/risk/document/NCR/CAPA regression:199/199 at0045 PASS.
- API Ruff format/lint and mypy66 files PASS;50 default unit tests PASS.
 355 integrations are skipped without their dedicated harnesses; the58+199 above
  were actually executed separately. Two existing dependency deprecation warnings.
- Web lint/typecheck,60 unit tests and production build PASS. No new dependencies.
- Final browser108/108 Linux +11/11 Darwin PASS, no retries/golden updates.
  Includes role-filtered paging, read-only/history after date changes, command
  confirmation/conflict/denial and375/1440px light/dark axe AA/overflow checks.
  This is scoped automated accessibility evidence, not full WCAG conformance.
  Mocked QMS writes never forward to the actual backend. Five actual synthetic
  screenshots and11 logs plus dependency JSON are in the encrypted checkpoint.
- Gitleaks working tree/history, license policy and changed-shell ShellCheck PASS.
  OpenGrep six Python rules over six changed application/migration files:0 findings;
  this is not a complete security/TypeScript audit. pnpm audit:one pre-existing
  Moderate minimatch advisory, zero High/Critical. Local health PASS.

The concurrency test first missed imports, then read a stale fixture ORM identity;
imports and cache expiry were corrected. A final history regression reproduced
retired activities being hidden after parent rescheduling; the client now applies
parent date bounds only to active activities, preserving historical intervals. Only the final58-pass run is acceptance
evidence. No business constraint or assertion was removed to obtain that result.

## Recovery and release limits

Source CP-AUDIT-AGENDA-00-20261113T044030Z and separate pre-migration DB
CP-AUDIT-AGENDA-DB-00-20261113T044043Z were restored before local migration.
The DB restoration verified0044,53 tables/47 forced RLS and all rows/schema/ACLs/
roles/sequences. The source image was no longer locally available: hardened
fallback postgres/pg_dump/pg_restore executables matched source SHA256. Only
constant varchar-array deparser equivalents and built-in pg_* bootstrap grantor
names are normalized; custom grants and row content are compared unchanged.

Local0044→0045 was applied explicitly after recovery proof. Old API/web images
remain tagged before-audit-agenda-20261112. Actual encrypted backups and separate
0600 keys remain outside the repository. A backup does not authorize rollback;
restoring operational data or changing images requires a reviewed recovery plan.
The original checkout's unvalidated0041 WIP is separate and must not be applied.

PR34/4d2e80f quality43365509636 and CodeQL43365509645 passed; security43365509662
failed only the final release gate. These results do not certify this new branch.
Exact-head CI, independent review and human approval remain required before merge.
No merge, production change, certification, readiness or complete QMS parity is
claimed. Next: independence/readiness, then execution/evidence/findings→NCR/CAPA.

Final source/Git/evidence checkpoint: **CP-AUDIT-AGENDA-06C-20261113T052847Z**. Post0045 DB
**CP-AUDIT-AGENDA-DB-06-20261113T051030Z** restored54 tables/48 forced RLS PASS.
Local screenshot paths: `artifacts/visuals/audit-agenda-linux/`; raw assets/logs are
ignored, encrypted externally and verified by hash, not committed as customer data.

## Checksum false positive and bounded scanner control

The first final manifest's API-test-log SHA256 was flagged as generic-api-key.
Its exact value was recomputed from the original log, proving it is an integrity
checksum, not a credential. Publication was held. A local commit was created
before noticing the nonzero scanner exit; it was not uploaded. No secret rotation
is indicated by this checksum-only finding, and no actual credential was exposed.

The exception now requires both that exact checksum and that exact historical
manifest path, and targets only generic-api-key. There is no directory-wide or
commit-wide suppression. Four executable controls prove detection without the
exception, allow the verified metadata, and detect a different value at the same
path or the same value elsewhere. The control is required in security CI and the
local checkpoint script. Gitleaks worktree/history both pass with that control.
An initial global-path configuration was rejected by the negative control and
never published; rule-targeted configuration is the verified final version.
See [Gitleaks8.30.1 configuration](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md#configuration).

The first458-source checkpoint remains immutable as recovery history. This
subsequent checkpoint includes the scanner correction and regression control.
Public evidence omits individual report hashes in the new manifest; private
recovery metadata retains them, with ciphertext hash and verification public.

Delivery: [draft PR35](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/35), stacked on PR34. Functional commit
`35674c9ff02727b48ffa9af91edea57a657daec7`, tree
`79003f8b7477c2dea0959fb8a0ecb04ff0d80e36` matched local exactly. This
follow-up records continuity only; exact new-head CI/review remain required.
