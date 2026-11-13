# Audit-specific competence assessments —13November2026

## Scope and policy

0048 adds a recorded human competence assessment for each planned auditor in one
internal audit. It is not a corporate training register or automatic verification
of professional credentials. A released document is controlled supporting material;
the reviewer must assess its relevance, the person's experience and the scope.
There are no fabricated qualifications, automatic signatures, grants or demo reviews.

Confirmation requires a scheduled audit, an active auditor assignment and local
user/membership, authored rationale, explicit attestation, validity covering both
today (UTC) and the audit's planned end, and a released clean document revision
from the exact same company/unit. Only audits.read + documents.read can inspect
this evidence-linked history; additionally audits.review is required to append.
The reviewer must be outside audit creation, leadership and the active team, as
a conservative engineering segregation policy for human review, not an ISO mandate.

Every decision appends. Withdrawal requires a prior confirmed assessment for that
assignment and a reason, and copies its exact source snapshots and validity. It
can retire an assessment for a withdrawn assignment or inactive member while the
audit is still planned; these people remain in the history-aware roster. Only
active auditors contribute to totals. A parent/assignment/plan change never rewrites
the historical assessment. Terminal audits receive no new decisions.

A current assessment must match the exact planning version, remain within its UTC
validity, retain active documentary support with the same hash, and retain active
subject and reviewer membership. Superseded revisions or obsolete documents make
support unavailable. Revoking a signer's review capability prevents new acts, not
retroactive deletion of a decision signed with authority; inactive signer membership
is separately reflected. This follows the existing independence distinction.

## Persistence, contracts and security

`qms_audit_competence_reviews` is forced RLS with SELECT/INSERT only. Runtime cannot
UPDATE, DELETE or TRUNCATE. Composite audit/document/revision FKs enforce company
and unit; invoker trigger independently verifies actor, subject assignment, current
plan, review sequence, eligibility, source state and validity. It captures document
code/title/revision/SHA256, assignment name and server time; actor identity must match
the current directory. Withdrawals preserve original evidence. No new SECURITY
DEFINER function, grant projection, DB role, capability or broad RLS policy is added.

`review_version` is global per audit and separate from parent row_version. Parent
locking serializes append/append and append/planning races. Both expected versions
are required. A review does not increment or otherwise edit the plan. Append and
technical internal_audit.updated event commit atomically; before/after use actual
preceding aggregate entries. Rationale is SHA256 in the ledger, with full narrative
only in authorized business history. No file object key or document bytes are added
to responses or events. The API follows the existing session/CSRF/same-origin rules.

Under `/internal-audits/audits/{id}`:

| Method/path | Behavior |
| --- | --- |
| GET `/competence` | Paginated history-aware roster, latest assessment/status, active totals, actor eligibility/global review version |
| GET `/competence/reviews` | Append-only history, limit1–50/offset |
| POST `/competence/reviews` | Confirm or withdraw against expected audit/global review versions |
| GET `/competence/documents` | Searchable paginated same-unit released/clean document choices |

All require audits.read + documents.read, including choices. All successful responses
are private,no-store. Confirmation input includes document/revision/valid_until;
withdrawal sends those as null and the server preserves them. Immutable identity,
snapshots and timestamps cannot be supplied through the JSON contract. The roster
includes prior assignments with history, while totals count only active auditors.
Page and totals are computed by one SQL statement/MVCC snapshot, including empty
pages. Grant revocation during GET maps to403/404 and clears client context rather
than producing an internal error or returning the cached evidence.

The existing preparation endpoint now reports the real competence count when the
actor has document read access; without it the check stays unverified and no
competence details are fetched. Passed means current recorded assessments exist,
not certification. **ready_for_execution stays literally false**. Future ready/start
commands must atomically revalidate competencies, permissions and plan constraints;
none can use this diagnostic as a durable authorization.

## Interface

Readiness now includes a compact roster, current/expired/outdated/withdrawn or
unavailable-source status, evidence picker/search/pagination, validity, rationale
and attestation. Historical decisions are folded and paginated. Reconciliation is
explicit after conflicts or uncertain responses;503 preserves an editable draft,
while401/403/404 clears the planning context. A mismatched2xx or unknown server
failure blocks blind retry. Read-only users have no command buttons. Missing
document read access produces a prerequisite without extra requests.

Saving competence refreshes preparation without editing/remounting the plan. An
open independence rationale is preserved while its diagnostics reload; if its
independence review version changed meanwhile, submission is blocked until explicit
refresh. An additional fix blocks independence replay after an ambiguous500,
including a scenario where the first command was already persisted. Unknown
failures are conservative;422/503 remain correctable/retryable. No ready/start or
new execution control appears.

## Evidence and remaining work

121 PostgreSQL audit cases (30 new competence cases),199 process/document/risk/NCR/
CAPA cases,50 default API unit cases and60 web unit cases passed.418 integrations
skipped in the default unit run are distinct from the320 executed through harnesses.
The qualification-file metadata is synthetic in disposable PostgreSQL; these tests
do not claim to exercise AV/S3 or substantiate the qualification's truth.

Independent read-only review of parent-authored implementation found two P2 issues:
separate aggregate/roster snapshots and an internal error on read-grant revocation.
Both were corrected and covered with deterministic concurrent-change regressions.
Other cases cover raw SQL/immutable history, self review, wrong company/unit/source,
expired/unclean/draft support, inactive people, former assignments, atomic event
rollback, one winning concurrent append/one409, and global totals on empty pages.
An existing0047 roundtrip test was corrected to restore head in finally; its older
assertions remain intact. A populated0048 downgrade is refused even when only its
technical history remains. Empty migration roundtrip runs only in disposable DBs.

Browser/visual final results are recorded in CHECKPOINT.md after execution. New
command cases intercept writes; real demo login/API reads are separate. No synthetic
human evaluation is inserted into the actual demo. Scoped axe checks and automated
scanners do not constitute WCAG, ISO27001 or NIST certification.

No dependency added. General training/certification records, expiry reminders,
ready/start transitions, execution evidence and finding→NCR/CAPA remain pending.
The prior production release gate remains failed and exact-head CI/human review
are required before merge. No production migration, merge or deployment occurs.

## Recovery

CP-AUDIT-COMPETENCE-00-20261113T182432Z restores481 sources+Git before edits.
PreDB CP-AUDIT-COMPETENCE-DB-00-20261113T182548Z restores0047/56 tables/49 forcedRLS.
PostDB CP-AUDIT-COMPETENCE-DB-06-20261113T184515Z restores0048/57 tables/50 forcedRLS.
Both isolated tmpfs/no-network/no-port restorations compare rows/schema/ACL/roles/
sequences. Fallback image is different, with identical postgres/pg_dump/pg_restore
executable SHA256; only equivalent constant varchar-array casts and builtin pg_*
bootstrap grantor names are normalized. Separate0600 keys/backups stay outside Git.
Before-audit-competence API/web images are retained. Local0048 was applied only
after pre-restore and121-pass proof. The reserved original0041 WIP remains separate.
Final source/evidence and exact delivered-head bundle are verified independently.

Final browser regression:140/140 Linux +10/10 Darwin PASS without retries or golden
updates, including9 competence cases and1 extra independence replay case. Scope:
375/1440px, light/dark, axeAA and overflow; root inspected desktoplight/mobile
dark captures. First6 focused failures were an exact-label test locator including
select option text; replaced with exact accessible combobox role without changing
application behavior, enabled checks or selected-value checks. Actual seeded API
readback confirms one auditor, zero fabricated evaluations, blocked competence and
readyfalse. Final snapshot/evidence identifiers and delivery are in CHECKPOINT.md.

Entrega [PR borrador39](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/39), sobre PR38/fbfd69a. Funcional95a9de70ccee0ae5018270e359ee388a6a43325e, árbol781ec472696e2f2277b5a9ce07c2b5bb20b5c1a4 idéntico local/remoto. CP-AUDIT-COMPETENCE-06B-20261113T190132Z restaura490 fuentes+Git y22 evidencias (5PNG/15logs/2JSON), con backups DB0047/0048 separados. Seguimiento solo documental; CI del head final y aprobación humana pendientes. Sin merge ni producción.
