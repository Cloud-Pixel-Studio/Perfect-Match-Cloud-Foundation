# Audit criteria · 12 November2026

## Implemented

Authorized planners can add ordered audit criteria: title, source type
(internal, standard, customer or regulation), source reference and an authored
requirement. Each criterion applies to the whole audit or an active scope item
from the same audit, company and unit. Reference metadata neither imports
licensed standards text nor verifies an edition/clause or commercial entitlement.

Creation, editing and reasoned withdrawal preserve history and advance the parent
audit version atomically with the criterion version and its technical event.
Only draft/planned audits accept changes. Withdrawn criteria remain readable
but cannot be changed or reinstated. Active criterion orders are unique; a
withdrawn order may be used by a new record with its own identity/history.

Scope withdrawal now refuses to orphan active linked criteria. Relink them to
another active scope, change them to whole-audit criteria or withdraw them first.
The guard also applies to direct runtime SQL. Parent locking serializes both
operations; scope and criterion links have composite company/unit/audit foreign
keys. Runtime has no delete/truncate authority on criteria.

Migration0043 follows0042; reserved0041 remains outside the chain. No Odoo,
authentication, commercial licensing, seat or subscription changes are included.
Team, agenda, independent review, readiness, execution, evidence, findings and
finding-to-NCR/Action Center integration remain pending. An audit with criteria
is still a planning record, not an execution-ready or ISO-certified audit.

## API and access

| Method | Path below `/internal-audits/audits/{audit_id}` | Result |
| --- | --- | --- |
| GET | `/criteria` | Paginated active/withdrawn or all history, limit1–50 |
| POST | `/criteria` | Create,201, expected_audit_version required |
| PATCH | `/criteria/{criterion_id}` | Edit with expected audit and criterion versions |
| POST | `/criteria/{criterion_id}/withdraw` | Reasoned retirement with both versions |

Writes return `{criterion, audit_version}` and retain the existing CSRF/session
requirements. Read requires audits.read; mutation also requires audits.manage
in the active organization unit. Seats and tenant roles imply neither.
Forced RLS hides cross-company/unit records and applies revocation immediately.

The technical append-only event is internal_audit.updated under the parent audit
ID. It includes criterion identity/order/type/scope/version/status and SHA256
hashes of title/requirement/reference/reason, not their narrative text. API change,
parent version and event share one transaction. SQL triggers enforce identity,
terminal immutability, valid active scope and parent-state/version invariants.
Downgrade refuses to remove any criterion row or recorded criterion-event history.

## UI and demo

Internal audits → Scheduled audits → select audit → Audit criteria.
Create/edit forms, active/history registers and scope-choice pagination reuse
existing components/tokens. A selected scope stays selected across pages. The
selector only requests active items in this exact audit; no search endpoint is
invented. Its whole-audit option is explicit.

409 and unknown success/network outcomes lock blind resubmission until an
explicit refresh retrieves the full parent/version. A concurrently cancelled
parent loses edit controls.503 preserves the draft without automatic retry;
401/403/404 closes cached authority. Responses are checked against audit/unit/
identity/version/status; requests from old/unmounted contexts cannot repopulate
another unit. Existing scope conflict feedback explains the linked-criterion guard.

The development-only seed uses real API commands. Two runs and authorized
readback confirmed exactly1demo program,1audit,1active process-linked scope and
1active internal criterion linked to that scope. Seed checks all history pages
and never resurrects a withdrawn demo or overwrites existing wording.

## Preservation and verification

- Baseline source/Git checkpoint CP-AUDIT-CRITERIA-00-20261112T233726Z:
  431entries restored by SHA256, Git bundle verify PASS. CP-AUDIT-CRITERIA-02-
  20261112T234627Z preserves437entries of WIP before GitHub integration.
- Separate pre-migration DB recovery CP-AUDIT-CRITERIA-DB-00-20261112T233748Z:
  isolated0042 restore,51tables/45forcedRLS, rows/schema/owners/ACL/roles match.
  Post-0043 backup identity/results are recorded in CHECKPOINT.md and manifests.
- Backups are encrypted outside the repository; separate0600 keys. Restoration
  uses a unique bootstrap role, no network/ports and tmpfs. PostgreSQL executables
  match source SHA256 in the fallback hardened image. Only equivalent constant
  varchar-array deparser casts and built-in pg_* bootstrap grantor names are
  normalized; row contents and custom grants are compared without relaxation.
- Local preview migrated explicitly0042→0043 after recovery PASS. Previous
  API/web images tagged before-audit-criteria-20261112 remain available. Image
  rollback does not undo DB history; use reviewed forward fixes or an isolated
  database restoration, never a blind downgrade of operational records.
- Dedicated PostgreSQL:31/31PASS (20existing+11criterion cases). Covers history,
  duplicate-order atomicity, stale versions, source validation, cross-audit/unit/
  company scope links, revocation, SQL restrictions and scope-retirement guard.
  Empty upgrade/downgrade and populated downgrade protection PASS.
- Process/risk/document/NCR/CAPA regression:199/199PASS at0043, with protected
  CAPA history downgrade. The previous PR32's missing scope-table cleanup was
  fixed separately at8c60a50 and verified199/199 at0042 before publication;
  this branch additionally includes criteria in that explicit test-only cleanup.
- API Ruff format/lint/mypy62 files and50default unit tests PASS;328integration
  tests skip in the default command lacking their dedicated harnesses. The31+
  199 database cases above actually ran in separate disposable databases.
- Web lint/types/build and60unit tests PASS. Full Linux87/87 and focused Darwin10/10 PASS, no retries or golden updates.
  Axe A/AA and overflow checks passed in the tested375/1440 light/dark forms;
  screenshots inspected. Ten new criterion fixtures intercept every QMS write;
  real API seed and live proxy read remain separate evidence.
- Gitleaks tree/history, license policy, ShellCheck PASS. Six Python OpenGrep
  rules/four changed application files0findings; not a full security or TS audit.
  No new dependencies; full dependency audit1pre-existing Moderate,0High/Critical.
- First harness run exposed process data left between test modules; cleanup now
  includes processes. A second failed due VM disk exhaustion;4.288GB unused,
  regenerable build cache was reclaimed without deleting volumes/data/rollback
  images. Test identities now use persistent IDs across rollback/context changes.
  Browser checks caught a missing explicit select label and a stale test selector;
  corrected, with final evidence recorded separately. No gates were weakened.

PR32/8c60a50 quality43360528455 and CodeQL43360528130 PASS; security still running
at inspection. This does not approve the new criteria head. Exact-head CI,
independent review and human approval remain required before merge. No production
merge/deployment or certification is claimed.

Post-0043 recovery **CP-AUDIT-CRITERIA-DB-06-20261113T034349Z** restored52tables/46forcedRLS,
including the demo criterion; row/schema/role checks PASS. Final source/Git/
visual checkpoint **CP-AUDIT-CRITERIA-06-20261113T034926Z**; public manifest records verification.

Entrega: [PR borrador33](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/33), sobre PR32/8c60a50. Commit funcional `da5f3aa9e44e2e630d178b1d3c07ed49e6d4e627`, árbol `8dbf955688d97604fea96b0d62bbee2b2121934d` idéntico local/remoto. Este seguimiento solo registra continuidad; CI exacto nuevo, revisión independiente y aprobación humana pendientes. Sin merge ni producción.
