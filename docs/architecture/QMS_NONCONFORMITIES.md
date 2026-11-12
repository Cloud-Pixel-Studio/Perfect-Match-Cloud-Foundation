# Nonconformity register and controlled lifecycle

Core implementation: migration `0023_qms_nonconformities`, API
`nonconformities.py` and `NonconformitiesWorkspace`, 2026-10-29. This is a partial
implementation of Odoo's NCR addon. Original model, workflow, access rules and tests
were reviewed in [`pm_qms_ncr`](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_ncr).

Migration `0024_ncr_links`, `ncr_links.py` and `NCRLinks` add related risks,
control implementations and released document revisions; migration
`0025_ncr_evidence_links` adds accepted implementation evidence. The Odoo source relates
these record types at the same organization scope. The SaaS records immutable
target code, name, process, version and (for documents) released revision and
scanned file digest. It retains reasoned removal history; subsequent target
closure or document obsolescence does not erase the snapshot. Evidence snapshots
retain only the implementation code, evidence name and accepted version; private
summary and review decision are not copied into link records or audit payloads.

Link reads require `ncr.read` and the matching target read capability
(`risks.read`, `control_instances.read` or `documents.read`). Accepted evidence uses
the existing `control_instances.read` authority of its source checklist. Link changes also
require `ncr.manage`, an active membership and a nonterminal NCR. Tenant/unit
composite keys and forced RLS enforce the scope in PostgreSQL; a related record
can belong to another process in the same unit. Closed risks can be referenced as
historical context. New control references require an active implementation; new
document references require an active, released and clean revision. Evidence references
require an accepted review from an active implementation; pending and rejected
evidence cannot be linked. Parent version
and link history advance together under a row lock, so closure and linking serialize.
The UI provides searchable, paged target catalogs and preserves its selections.

## Record and scope

Each NCR belongs to one tenant, organizational unit and process. It records a code,
title, description, origin (internal/customer/supplier/process/product/document/audit/
other), severity (minor/major/critical), detection date, detector, responsible person
and target date. Code is unique within the tenant, ignoring case. The application
captures the detector from the signed-in actor; the browser cannot supply another
detector or replace scope, code or creation identity after creation.

Containment records include whether it is required, its action, optional owner,
completion date and completion flag. Investigation retains root-cause summary,
disposition and disposition notes. Dispositions match the source addon: use as is,
rework, repair, return, scrap, information only or other. Narrative fields are bounded
at 4,000 characters. Creation requires an active scoped process; existing NCR follow-up
can continue after process archive while the unit and grants remain active.

## Workflow and validation

| Current state | Allowed next states | Authority |
| --- | --- | --- |
| draft | open; cancelled | manage to open; review to cancel |
| open | containment; investigation; cancelled | review |
| containment | investigation; cancelled | review |
| investigation | action_required; cancelled | review |
| action_required | verification; closed; cancelled | review |
| verification | closed; cancelled | review |
| closed / cancelled | none | preserved terminal record |

The source Odoo form permits closure from action required or verification; this
implementation preserves that option. Entering containment requires its flag to be
required. Required incomplete containment blocks investigation and closure.
Completion requires a nonblank action and a completion date. Once opened, a required
containment flag cannot be lowered to bypass that gate; this is an explicit SaaS guard
in addition to the source behavior. The owner remains optional, matching source scope.

Closure requires notes, which a reviewer may submit in the closure command without
separate edit authority. Cancellation stores the required decision as its reason.
Opening, review, closure and cancellation retain their actors/timestamps. A separate
human reviewer is not mandated by the source NCR module; the SaaS separates authority
with explicit capabilities. Document and control-evidence independent review rules
continue to apply to their own records.

Closed and cancelled records cannot be edited, reopened or deleted by the application.
Daily overdue status is computed live from the current UTC date and becomes false in
terminal states. It is not a stored flag that becomes stale overnight.

## Access and integrity

- `ncr.read` is required by API reads. Creation/editing/opening require `ncr.manage`;
  all other transitions require `ncr.review`. Creation also requires `processes.read`.
  Tenant owner, seats, detector and record owner receive no implicit QMS authority.
- Forced PostgreSQL RLS enforces tenant/unit scope. Manage/review grants also provide
  the row visibility required for database writes; API read operations still require
  the explicit read grant. Auditors can receive read grants only.
- Composite foreign keys enforce process alignment. Responsible person and containment
  owner must be active members of the tenant when assigned. Cross-tenant identifiers
  and inactive/mismatched processes are rejected.
- API row locks and `expected_version` reject stale edits. Database triggers require
  exact one-step version changes, valid transitions, containment gates and current
  workflow actors; direct status/history edits and terminal rewrites are rejected.
- Mutations and audit events commit together. Descriptions, containment actions,
  investigation, closure notes and cancellation reason use SHA-256 audit fields.
  Workflow decisions are limited to 500 characters. An audit failure rolls back the NCR.

## API and UI

The register uses `GET/POST /nonconformities`, detail/edit use
`GET/PATCH /nonconformities/{id}`, and commands use
`POST /nonconformities/{id}/transition`. Lists require a unit and support literal
code/name search, source/severity/state filters and bounded pages of 50. Offset is
bounded at 1,000,000. Concurrent inserts can reorder pages, requiring refresh.

The interface groups identification, containment, investigation/disposition and
workflow. It offers paged process/member catalogs, preserves chosen references during
catalog searches, ignores stale scope/tenant responses and clears data after denied
access. It shows allowed workflow options according to the user's grants and the
current containment gate. Terminal records remain readable for traceability.

## Evidence and remaining parity

The disposable PostgreSQL suite passed **154 tests**, including **28 NCR core tests**,
**44 NCR link tests** and **two accepted evidence link tests**; log:
`artifacts/ncr-evidence-integrity.log`. It checks lifecycle, authority, tenant isolation,
direct-write rejection, stale versions, containment bypass, terminal immutability,
audit rollback and literal search. Migration round-trip to `0008` passed before
business writes; downgrade across business audit history is intentionally rejected.

`scripts/runtime-ncr-e2e.py` passed with real local author/reviewer OIDC sessions and
the web proxy, including owner-without-read denial, author-without-review denial,
containment gates, stale conflicts, closure notes and audit events. Synthetic records
were closed, temporary grants revoked and test sessions logged out. The optional
`--visual-hold` pauses before cleanup; press Enter to release the hold and perform
cleanup. `scripts/runtime-ncr-links-e2e.py` passed with a historical closed risk,
active control implementation and a real scanned, independently released PDF. It
checks target permissions, proxy access, snapshots, reasoned removal/relink, closure
and history after document obsolescence. Synthetic test grants were revoked and
sessions closed. The same OIDC run now links independently accepted implementation
evidence; pending evidence cannot be linked. Static checks, nine audit unit tests,
web lint/types/eight tests/build and local
health passed. An independent code review found no actionable core defects.

Interactive browser acceptance remains pending: its previous session had expired
during the visual check. Automated HTTP coverage does not establish visual acceptance.
See `CHECKPOINT.md` for the wider security/release limitations.

Still pending: audit-finding provenance; creation/linkage of CAPA; controlled attachments,
reporting, notifications and full Odoo parity. Codes are entered by the user and made
unique within a tenant; Odoo-style automatic sequence allocation is also pending.
There is no arbitrary attachment upload endpoint or placeholder CAPA action in this slice.
