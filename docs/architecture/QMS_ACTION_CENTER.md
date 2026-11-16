# QMS Action Center

## Implemented boundary

The Action Center is a read-only projection over existing controlled records. It does
not create a second task table and therefore does not become an alternate source of
truth. `GET /action-center` combines:

- active workflow task and approval steps;
- open/in-progress CAPA actions and completed actions awaiting independent verification;
- incomplete control implementation activities; and
- submitted implementation evidence awaiting independent review.

Each item retains its source identifier, current state, owning unit where applicable,
responsible user when one exists, due date, urgency and destination workspace. The
dashboard and full Action Center consume the same API. Destination metadata separates
the actionable child from its parent record, process and unit so navigation can open
the exact authorized record rather than only its module.

## Authorization and isolation

- Request context is established with the authenticated user and selected tenant.
- PostgreSQL forced RLS remains authoritative for every source query.
- “My actions” applies source-specific assignment rules and explicit review
  capabilities. It does not turn read access into mutation authority.
- CAPA verification and evidence review exclude the submitting/completing user from
  their personal queue, preserving segregation of duties.
- Evidence-review actions are emitted only when the reviewer also has the control
  and implementation read/manage context required to open and complete the exact
  destination. An `evidence.review` grant alone never creates a dead-end action.
- Workflow eligibility matches the workflow engine's user, application-role and active
  organization-unit assignment resolution in SQL before pagination. Auditors do not receive executable
  workflow actions in their personal queue.
- “Team view” is limited to owner, admin and auditor membership roles. It is oversight
  only; source endpoints still enforce their own capabilities before any mutation.
- Assignee names come from the tenant-scoped organization member directory function,
  not from unrestricted user-table access.

Commercial seats are intentionally absent from authorization decisions. A seat or
tenant role never grants a QMS capability.

## Prioritization contract

Items are ordered by overdue, waiting review, due within seven days and normal work,
then due date and most recent source update. Dates are evaluated server-side in UTC.
The summary reports all authorized matching records even when the returned item list
is capped for the compact dashboard.

### Integrity update ·16 November2026

Eligibility and exact unit scope precede pagination for all four sources. One
read-only SQL statement combines the eligible set, complete counts by source and
the bounded page, so a page and its summary use the same PostgreSQL statement
snapshot. There is no250-row preselection or unbounded Python materialization.
The client limit(1–200) limits items only. Empty queues retain zero totals and{}.

CAPA planning actions remain visible in action_planned/implementation; in-progress
and pending-verification actions require an implementation parent. Cancelled,
closed, effectiveness-review and other non-actionable parents are excluded.
Personal execution requires the assignee and manage capability; personal review
requires review authority and a different completer. Read-only oversight remains
available in team view to the authorized role with destination read capabilities.

Controls require both control and implementation read context; personal activities
also require implementation management. Personal evidence review retains all four
capabilities and submitter/reviewer separation. No grants, commercial roles, RLS
policies or mutations are introduced. Tenant/actor activity is rechecked at return.

Workflow instances have no business-unit resource scope. A unit-filtered query
therefore excludes them; an assignment to an organizational unit is not a resource
scope. The unfiltered personal/team views still include eligible workflows.

Evidence:18 dedicated real HTTP/PostgreSQL tests, including251-row ownership
starvation,251 eligible rows with limit1, all four sources outside the first page,
terminal parents, reviewer independence, revocation, tenant suspension/isolation
and user/role/unit assignments;31 existing Workflow integrations PASS. Full API
unit suite93PASS/530DB cases skipped without their dedicated harnesses. The18/31
DB results above are separate actual harness runs, not those skips.

Local development preview uses only the two corrected queue modules plus the
earlier process-form fix over PR39/DB0048. No schema, business data, grants or
production update. Ten authenticated live read checks PASS (operator/reviewer,
limit1 vs200, unit filtering, team403, parent states). This is not complete browser,
load-test or security acceptance. See product/ACTION_CENTER_INTEGRITY.md for scope.

## Verification status

Implemented and locally verified:

- deterministic urgency and summary unit tests;
- API import and route registration;
- disposable PostgreSQL integration coverage for assignment, exclusion of unrelated
  work and isolation of the same user across two tenants;
- Ruff formatting/lint and strict mypy for changed backend sources;
- web unit tests, lint, typecheck and production build;
- responsive, accessible loading, empty, error, personal and team states in code; and
- authenticated Linux Playwright/axe coverage for the responsive empty state, with
  no accessibility violations or horizontal overflow. The reviewed desktop and
  mobile captures are the accepted Linux baselines; and
- exact, refreshable URL targets for workflow instances, CAPA actions, control
  activities and evidence reviews. Point reads remain tenant-scoped and capability
  protected; PostgreSQL integration tests cover cross-tenant hiding.

Pending before acceptance:

- authenticated browser visual regression for populated personal/team queues;
- regenerated Darwin baselines from a source runtime;
- real-user, keyboard and screen-reader acceptance.
