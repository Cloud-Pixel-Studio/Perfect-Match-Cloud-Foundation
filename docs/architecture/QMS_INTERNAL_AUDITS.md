# QMS internal-audit architecture

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
2. Scope, criteria, agenda/team and independence review.
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

This milestone is backend planning infrastructure only. Scope, criteria, team,
independence decisions, evidence, findings, NCR handoff, Action Center exposure,
demo data and the premium UI remain later slices and must not be presented as
implemented.

## Slice 2 verified reference and SaaS rules

The secondary Odoo repository was re-read at
`d89330cc1a8e9a2ea16992c9b49394f1dc481b7f` before designing the next slice.
Its source defines normalized scope lines, typed criteria, lightweight agenda
lines, auditor/auditee membership, and explicit independence confirmation or
documented override. Those are functional references only; the SaaS will not
copy Odoo ACLs, models or infrastructure.

The SaaS slice will enforce these stronger invariants:

- Scope lines inherit the audit tenant and unit, may reference an in-scope
  process and control implementations, and are mutable only in `draft` or
  `planned`. A withdrawal is retained rather than deleting history.
- Criteria are typed as internal control, company procedure, customer
  requirement, regulation, external standard reference or other. External
  standards store metadata only: identifier, edition and clause/reference.
  Licensed requirement text is never seeded or copied.
- Agenda lines use bounded duration minutes, an optional in-scope process, an
  active tenant auditor, an optional active auditee and customer-authored notes.
- Team membership is explicit and scoped. A tenant role or paid seat cannot add
  someone to an audit team and cannot substitute for `audits.execute`.
- Independence is a review command, not an editable checkbox. Confirmation and
  override both require `audits.review`; an override requires a reason. The
  reviewer cannot be the lead auditor, and the recorded actor/time are immutable.
- `planned -> ready` requires an active scope line, an active criterion, an
  active lead auditor represented on the team, and a confirmed or documented
  independence decision. Direct state updates remain forbidden in PostgreSQL.

Execution transitions, evidence and findings remain outside this slice so that
readiness cannot be confused with completed fieldwork.
