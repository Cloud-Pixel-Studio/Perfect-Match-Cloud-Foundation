# Independence assessment and preparation diagnostics -13November2026

>0048 follow-up adds audit-specific recorded competence assessments; see
>AUDIT_COMPETENCE.md. This historical slice does not itself implement them.
>Ready/start/evidence/findings remain unavailable.

> Historical0046 scope below.0047 now implements scoped execution-access counts;
> see AUDIT_EXECUTION_AUTHORITY.md. Competence and execution workflow remain blocked.

## Implemented boundary

Migration0046 follows0045; the reserved/unvalidated0041 remains outside the chain.
Reviewers can record an independence assessment, a documented conflict exception
with mitigation, or a reasoned withdrawal. Every command appends an immutable
record and technical event. This records an authorized human assessment; it does
not automatically prove process-owner independence, qualification or conformity.

The conservative implementation policy requires audits.read+audits.review and a
scheduled plan. The reviewer must be outside audit creation, leadership and every
active team assignment. This creator restriction is an engineering segregation
choice for product/security review, not an ISO requirement asserted by the user.
An override cannot waive these self-review/authority restrictions. Confirmation
and override require explicit attestation, an active company lead assigned as a
planned auditor, active company participants, and active scope/criteria/agenda.
All decisions require authored notes, including withdrawal. There are no external
reviewer contacts, automatic invitations or automatic demo attestations.

## Versions, API and legacy fields

Below `/internal-audits/audits/{audit_id}`:

| Method/path | Contract |
| --- | --- |
| GET `/independence` | Current assessment, actor eligibility and preparation checks |
| GET `/independence/reviews` | Append-only history, limit1-50/offset, newest first |
| POST `/independence/reviews` | Expected audit+review versions, decision/notes/attestation |

The review is a separate aggregate. `review_version` increases exactly once per
append, while `source_audit_version` binds it to the exact planning revision.
Reviewing does not edit the plan or increment its version; the result contains
`{review, audit_version}` with the same planning version. Parent locking serializes
review/review and review/planning races. Stale expected review or plan versions
are rejected. Each actual plan/child edit already advances the planning version,
so prior assessments become outdated without rewriting their history.

The GET projection additionally marks the assessment not current for a closed
plan, a withdrawn latest decision or a reviewer absent from the active company
directory. Revocation of an actor's review responsibility immediately prevents
new decisions. Authority at signing time is distinct from current execution
permissions; historical assessment data never grants capabilities.

The existing parent independence fields are reserved legacy metadata. They are
not updated or trusted as this assessment's current projection.0046 blocks new
forged changes to those fields even through runtime SQL, without overwriting any
old values. Consumers must use the independence endpoint, source version and
`review_current`, never a static legacy flag to authorize operations.

## SQL, authorization and events

`qms_audit_independence_reviews` has forced RLS, exact company/unit/audit identity,
unique audit+review version, reviewer/lead identity snapshots and no runtime
UPDATE/DELETE/TRUNCATE grants. SQL independently enforces actor/current authority,
reviewer snapshot, scheduled/current plan, sequence, active lead/team/plan content,
attestation and reason rules. No new SECURITY DEFINER function or visibility into
other people's capability grants was introduced. Tenant roles and seats do not
confer QMS authority. Existing session/CSRF/same-origin defenses are reused.

Each append and internal_audit.updated event commits atomically. Before/after
values use the actual preceding review, including its narrative hash. Legacy
status fields are omitted from review-specific events to avoid contradictory
projections. Notes enter the ledger as SHA256, not raw narrative. Reviewer name
snapshots and authored notes remain in authorized business history. Destructive
downgrade refuses review rows or event history. Empty migration roundtrip is only
tested in disposable databases; no populated local downgrade was attempted.

## Preparation is diagnostic

The endpoint checks scheduled state, active scope, criteria, agenda, active lead/
company participants, a linked program's approved/active status and the current
independence assessment. Standalone planning is allowed. Counts stay within the
authorized audit; agenda does not validate a company-wide calendar.

`ready_for_execution` is deliberately always false. Current execution capability
for each planned auditor remains unverified because another person's grants are
not exposed through existing RLS. Competence/qualification records are not yet
implemented. Ready/start/evidence workflow commands are not implemented either.
The UI labels these checks unverified/blocked and exposes no ready/start command.
A future execution implementation must validate them, not replace them with a
checkbox, paid seat, company role or the independence attestation.

## UX and demo

Scheduled audits -> select audit -> Independence and preparation. Current,
outdated, override and withdrawn decisions are distinguished. Preparation checks
and paginated review history are collapsible to reduce detail-page length.
Read-only users can inspect diagnostics/history without command controls.
The form requires rationale and a conscious, keyboard-operable attestation.

401/403/404 clears the parent planning context.409 blocks replay until explicit
refresh reconciles the complete parent and review history.503 preserves draft;
network/unconfirmed/mismatched2xx blocks blind replay. Confirmation validates
actor, audit/unit, both versions, decision, notes and attestation. Late responses
are invalidated across scope changes and unmounts. Existing light/dark tokens,
loading/error/empty/success states and native accessible forms are reused.

The synthetic demo was read through the real authenticated proxy after0046:
one program/audit/scope/criterion/auditor/activity, no independence reviews or
invented human signature. Competence/access are unverified and execution blocked.
Seed code was unchanged; no additional grants, decisions or demo data were created.

## Evidence and limits

- PostgreSQL75/75 audit integrations, including17 new review tests, PASS.
  They cover reviewer-only authority, self-review denial, tenant/unit isolation,
  revoked grants/membership, stale plan/history, atomic ledger rollback,
  before/after hashes, immutable SQL history, forged legacy flags, terminal plans
  and concurrent requests (one append, one409). Empty roundtrip/history guard PASS.
- Process/risk/document/NCR/CAPA199/199 at0046 PASS. API Ruff/mypy68 files,50 default
  unit tests PASS;372 integrations skipped without their dedicated harnesses are
  separate from the75+199 actually executed. Two existing dependency deprecations.
- Frontend lint/types/build,60 unit tests PASS. Final browser118/118 Linux+10/10 Darwin PASS, no retries/golden updates,
  with375/1440px light/dark/axe AA and keyboard attestation checks. These are scoped
  checks, not complete WCAG conformance. One additional visual case passed after
  setting initial screenshot scroll; no application change or golden update.
  New browser commands use intercepted writes; the real API readback is separate.
- Initial test setup missed the imported fixture; test-only errors were corrected.
  A self-grant attempt correctly failed existing policy, and a membership test
  used the wrong enum before correction to revoked. A browser pagination wait
  matched Review10 before Review1. The exact visibility assertion then exposed
  history collapsing on pagination because loading unmounted its details element.
  History now stays mounted with a loading state, preserving expansion. Rules were
  not weakened. Only final successful runs count as acceptance evidence.

Quality/CodeQL on PR35/43df607 passed (43372682476/43372682175). Security43372682289
failed only Enforce final release gates; all previous steps, including isolated
runtime/browser/ZAP, passed. Do not inherit those PASS to this new code. Exact-head
CI, independent review and human approval remain required; no merge/production.
Odoo parity is still partial (historical20 blocks:11 partial/9 without a vertical).

## Recovery

CP-AUDIT-INDEPENDENCE-00-20261113T124751Z restored461 source files/Git before edits.
CP-AUDIT-INDEPENDENCE-DB-00-20261113T124853Z restored0045/54 tables/48 forced RLS.
CP-AUDIT-INDEPENDENCE-DB-06-20261113T130947Z restored0046/55 tables/49 forced RLS.
Rows, schema, roles, ACLs and sequences matched in isolated tmpfs/no-network/no-port
restoration. The hardened fallback's postgres/pg_dump/pg_restore matched source
SHA256. Normalization only covers equivalent constant varchar-array deparser
casts and built-in pg_* bootstrap grantor names, not customer rows or custom ACLs.

Local0046 was applied only after pre-restore and75-pass proof. Previous API/web
images before-audit-independence-20261113 remain. The final API ledger refinement
changes no DB schema/data. Encrypted backups and separate0600 keys stay outside
Git. Recovery remains a reviewed operation, not automatic downgrade with history.
The original0041 WIP is preserved in its checkout and recovery branch6b10edff.

Final source/Git/evidence checkpoint: **CP-AUDIT-INDEPENDENCE-06-20261113T133559Z**. Five synthetic PNG and11 logs
plus dependency JSON encrypted externally and restored by hash. See public manifest.
Local captures: `artifacts/visuals/audit-independence-linux/`.

Delivery: [draft PR36](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/36), stacked on PR35. Functional commit
`0bd870324c5bc7b53c322381497f7c95edecbefc`, tree
`17acc74ad4f047e2b961420975b3164c3f33630a` matched local exactly. This follow-up
records continuity only; exact-head CI, independent review and human approval
remain required before merge. No production changes.
