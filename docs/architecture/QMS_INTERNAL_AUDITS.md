# QMS internal-audit architecture

## Current verified implementation

As of13November2026,0040 planning UI,0042 scope,0043 criteria,0044 team,0045 agenda and0046 independence assessments are implemented.
Scope includes process references, versioned editing/withdrawal, forced RLS and
technical events. See `../product/INTERNAL_AUDIT_SCOPE.md` for contracts and proof.
Criteria support authored source references, whole-audit or active scope links,
versioned editing and reasoned withdrawal. See `../product/INTERNAL_AUDIT_CRITERIA.md`.
Planning team supports auditor/auditee roles, immutable identity snapshots and
versioned retirement; assignment does not grant execution access.
Agenda has versioned UTC intervals, active participant/scope links and within-audit
overlap guards; see `../product/INTERNAL_AUDIT_AGENDA.md` for tested boundaries.
Independence0046 uses append-only assessments bound to the plan version, with a
separate review version and conservative diagnostics. Readiness is always blocked
until competence, execution authority and workflow are verified. See
`../product/INTERNAL_AUDIT_INDEPENDENCE.md`; legacy parent flags are not authoritative.
The final readiness/execution/finding invariants below describe the
target architecture; they are not implemented by these planning slices.0041 remains
a reserved unvalidated recovery draft and must not be applied.

## Boundary

Internal audits are operational QMS records. They are not the append-only
technical `audit_events` ledger, and they do not contain licensed standards
text. Criteria may reference a standard, customer, regulation, internal
control, process or controlled document using metadata and customer-authored
wording only.

The verified Odoo reference separates program, audit, scope, criterion, plan,
evidence and finding. The SaaS keeps that functional boundary while applying
its own PostgreSQL RLS, explicit capabilities, optimistic concurrency and
append-only event architecture. No Odoo dependency is introduced.

## Traceability

```text
Audit program
  -> Internal audit
       -> scope + criteria + agenda + team
       -> evidence
       -> findings
            -> NCR (only internal nonconformities)
                 -> CAPA
```

Audit report completion is independent from finding, NCR and CAPA closure. A
completed audit may retain open follow-up work, which remains visible in the
Action Center.

## Capabilities and segregation

- `audits.read`: read permitted program, audit and subordinate records.
- `audits.manage`: create programs/audits and maintain planning data.
- `audits.execute`: collect evidence and draft findings while assigned to the
  audit team.
- `audits.review`: review independence, issue findings and complete reports.
- NCR creation also requires `ncr.manage`; an audit capability never implies
  corrective-action authority.

Commercial seats and tenant roles do not grant these capabilities. RLS applies
tenant and unit scope on every table. The lead auditor cannot approve their own
independence review; any documented override requires a reason and a different
reviewer.

## Workflow invariants

Programs: `draft -> approved -> active -> completed`, with controlled
cancellation before completion.

Audits: `draft -> planned -> ready -> in_progress -> reporting -> completed`.
Readiness requires scope, at least one criterion, a lead auditor and an
independent review or documented override.

Findings: `draft -> issued -> accepted|action_required -> closed`. Only issued
findings classified `nonconformity` with severity `minor|major|critical` may
create an NCR. Conformity, observation and opportunity-for-improvement findings
cannot create NCRs.

All state changes use commands, capture actor/time/reason, advance exactly one
row version and append a technical audit event. Closed/cancelled records are
immutable. Destructive downgrades are rejected after operational history exists.

## Delivery slices

1. **Implemented and tested locally:** program and audit planning schema,
   capabilities, forced RLS, optimistic versions, controlled program lifecycle,
   audit scheduling/cancellation and append-only technical events.
2. **Scope implemented:** ordered, versioned process-linked items and reasoned
   withdrawal/history. Criteria0043 are implemented; Team0044 planning is implemented; agenda0045 and independence0046 assessments are implemented. Execution remains blocked.
3. Evidence and finding execution with traceable snapshots.
4. Finding-to-NCR handoff and Action Center integration.
5. Premium responsive workspace, demo records and regression coverage.

Each slice must pass tenant isolation, cross-unit denial, revoked-capability,
optimistic-concurrency, transition and audit-history tests before UI exposure.

The first slice passed its dedicated disposable-PostgreSQL suite on 11 November
2026. The suite uses two tenants, two units in the primary tenant and separate
manager, reviewer and auditor identities. It proves that `audits.manage` without
`audits.read` cannot create records, that RLS hides cross-tenant and cross-unit
records, that revoking read access is effective immediately, and that the
auditor tenant role cannot receive manage/review capabilities. It also verifies
state-command guards, terminal immutability, duplicate/scope constraints,
optimistic versions, event counts and fail-closed downgrade after history.

At the original0040 milestone, scope/criteria/team/UI were later slices. The
current implementation at the top supersedes that historical boundary;
independence assessment is now implemented; final readiness and execution remain pending.


## Planning workspace · 12 November2026

`codex/internal-audit-planning-ui` exposes the existing0040 contracts through
Internal audits in Quality operations. This is separate from the technical
Audit trail. Programs and scheduled audits have separate scoped, paginated
registers; only program search is supported by the current API. Creation,
edits and controlled planning decisions use explicit unit capabilities.
The workspace does not expose execution/readiness, team/independence review,
evidence, findings or finding-to-NCR commands. Lead assignment does not establish
independence. See `docs/product/INTERNAL_AUDIT_PLANNING_UI.md` for evidence,
local0040 activation, encrypted recovery proof and remaining scope.

## Scope delivery0042

See `../product/INTERNAL_AUDIT_SCOPE.md`. No ready/in_progress/reporting command
was added. The full parent is reconciled after conflicts so a concurrently
cancelled audit does not retain scope-edit controls. Only local preview schema
and synthetic demo records were updated, after isolated recovery verification.

## Criteria0043

Source type/reference and authored requirements are metadata, not verified
licensed standard content. Active criteria can reference an active scope only
in the same audit/company/unit. Scope withdrawal is blocked while active criteria
remain linked. Parent locking serializes both operations; SQL and API enforce
the invariant. No readiness/execution command was added.

## Planning team0044

See `../product/INTERNAL_AUDIT_TEAM.md`. Lead remains the parent field. Active
auditees cannot become lead and lead cannot become auditee. Planning assignment
does not grant access/qualifications/independence; no target-grant query or new
definer function bypasses grant RLS. Future readiness checks must revalidate
current authority and reconcile lead/team.
