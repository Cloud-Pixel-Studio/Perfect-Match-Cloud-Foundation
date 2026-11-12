# Risks and opportunities — initial SaaS implementation

Implemented in migrations `0021_qms_risks` and `0022_risk_links`, API `risks.py` /
`risk_links.py` and `RisksWorkspace`. Updated 2026-10-29. This is partial Odoo parity. Primary source reviewed:
[`pm_qms_risk`](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_risk).

## Scope and authority

- Each record belongs to one tenant, organizational unit and process. A composite
  foreign key enforces that scope. Code is unique within the tenant, ignoring case.
  Identity, code, scope, scoring model and creation metadata are immutable.
- Explicit capabilities are `risks.read`, `risks.manage` and `risks.review`.
  API reads require read; create/edit require manage; state changes require review.
  Creation also requires `processes.read` and an active scoped process. Seat, tenant
  owner, process owner and assigned risk owner receive no implicit authority.
- Forced PostgreSQL RLS protects the table. Manage/review grants permit scoped row
  visibility needed by writes; API reads still require the explicit read capability.
  Auditors can receive read grants only. Owners must be active tenant members when
  assigned. No delete or truncate permission is granted to the application.
- Existing risks can be followed up and closed after their process is archived while
  the organizational unit/grants remain active. New risks require an active process.

## Data and lifecycle

Records retain risk/opportunity type, category/source, description/cause/effect or
benefit, response strategy/plan, responsible person and target/review dates. Scores
use probability and impact of 1–5, with separate initial and residual ratings.
`PMC-RISK-5X5-v1` and thresholds 5/10/16 are fixed snapshots on each record; there is
no shared mutable global threshold. Tenant-specific configurable policies are pending.
Scores and levels are derived in the API response; overdue days are computed from the
current UTC date so they do not become stale stored fields.

```text
draft → assessed → action_required → monitoring → closed
                  ↘ monitoring       ↘ action_required
```

Monitoring also supports an audited recurring review without changing state. Commands
record assessment/review/closure actors and timestamps. Closure requires nonblank notes;
closed records are immutable. API and database both reject skipped states, direct status
edits, scope changes and versions that do not advance exactly once. A separate review
grant is required; the Odoo risk module does not mandate a different human reviewer,
so this slice does not add that independent-person rule. Existing independent document
and evidence reviews remain in force.

Every mutation writes its audit event in the same transaction. Free-text narratives and
source are hashed in audit; workflow decisions are limited to 500 characters. Row locks
and `expected_version` reject stale updates. Failed audit writes roll back the risk.

## API and interface

- `GET /risks?unit_id=...&q=...&state=...&risk_type=...&limit=50&offset=...`
- `GET /risks/{id}`
- `POST /risks`
- `PATCH /risks/{id}` with `expected_version`
- `POST /risks/{id}/transition` with expected version, target state and decision;
  closure notes can be supplied atomically by a reviewer.

Search treats SQL wildcard characters as literal text. Pages contain at most 50 rows;
offset is bounded at 1,000,000. Concurrent inserts can reorder pages, requiring refresh.
The UI exposes scoring, narratives, dates, scope selection, process/member search,
editing and allowed workflow commands. Process and person selections survive catalog
search/page changes. Tenant/scope changes discard stale responses; revoked access clears
the visible register. A successful creation selects its code through a focused search.

## Evidence and remaining work

- Disposable PostgreSQL: 80 tests passed across process/document/control/risk/link suites,
  including risk isolation, roles, explicit grants, scores, versions, lifecycle, atomic
  audit, literal search/pages, closed immutability, closure after process archive,
  link snapshots, target read authority, soft removal, historical revision retention,
  rollback of link plus parent version, and concurrent closure/link serialization.
  Migration head → 0008 → head passed before business data; downgrade across risk audit
  history was rejected as intended.
- Local OIDC/API/web E2E passed for author/reviewer capability separation, score results,
  tenant owner without risk authority, stale write denial, monitoring, closure, audit and
  same-origin proxy. Extended controls E2E also passed real AV/scanned/released PDF risk links, soft removal, and historical reference after obsolescence. Synthetic DEV-E2E risks were closed; temporary grants revoked and
  test sessions logged out.
- Backend Ruff/mypy, web lint/types/tests (8) and production build passed. Browser
  confirmed the new module's no-access state; the authorized interactive browser flow
  remains pending. HTTP E2E is not visual acceptance.
- Not yet implemented: tenant scoring policies with approved versions,
  NCR/CAPA creation and linkage, reporting,
  exports, notifications or full Odoo risk parity. No certification claim is made.

## Related control implementations and controlled revisions (0022)

- Many-to-many relationships use the risk's tenant and unit. Related records may
  belong to a different process within the same unit, matching Odoo's organization
  boundary. Composite FKs and forced RLS reject relationships across tenants/units.
- Adding/removing a link requires `risks.read`, `risks.manage` and the target's
  `control_instances.read` or `documents.read` grant. Link reads require both risk and
  target read authority. Risk authority never expands target access; revocation hides
  linked metadata as well as preventing new relationships.
- A new link requires an active implementation or an active document with a released,
  clean revision under the transaction's read snapshot. DB triggers capture code,
  title/name, target process and row version; document links additionally capture the
  revision identifier and SHA-256. Client-supplied snapshots cannot replace them.
- Snapshots remain immutable when a target is renamed, retired or superseded. Link
  responses also show its current status, so a historical reference is not presented
  as a currently released document. No storage key is exposed. Link presence alone
  does not certify that a risk has been treated or resolved.
- Removing a link requires an explanation and preserves original fields, actor/date
  and reason. Removed records cannot be changed; adding the same target later creates
  a new record. Only one active relationship per risk/target is allowed.
- Each mutation locks the parent first, checks its expected version and rejects closed
  risks. The trigger advances the parent version exactly once; link and audit commit
  together. A concurrent close prevents a waiting stale link request from writing.
- Endpoints: `GET/POST /risks/{id}/control-links` and `/document-links`, with reasoned
  removal at `POST .../{link_id}/remove`. Lists have bounded pages; the implementation
  candidate catalog now supports literal code/name search and offset pagination.
- UI selectors retain choices across pages, show snapshots/current state and removed
  history, and hide each target section's data without its read grant. Mutations update
  the parent version and disable competing edits. Authorized browser walkthrough is
  still pending; automated API/database checks do not establish visual acceptance.
