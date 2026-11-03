# QMS Action Center

## Implemented boundary

The Action Center is a read-only projection over existing controlled records. It does
not create a second task table and therefore does not become an alternate source of
truth. `GET /action-center` combines:

- active workflow task and approval steps;
- open CAPA actions and completed actions awaiting independent verification;
- incomplete control implementation activities; and
- submitted implementation evidence awaiting independent review.

Each item retains its source identifier, current state, owning unit where applicable,
responsible user when one exists, due date, urgency and destination workspace. The
dashboard and full Action Center consume the same API.

## Authorization and isolation

- Request context is established with the authenticated user and selected tenant.
- PostgreSQL forced RLS remains authoritative for every source query.
- “My actions” applies source-specific assignment rules and explicit review
  capabilities. It does not turn read access into mutation authority.
- CAPA verification and evidence review exclude the submitting/completing user from
  their personal queue, preserving segregation of duties.
- Workflow eligibility reuses the workflow engine's user, application-role and active
  organization-unit assignment resolution. Auditors do not receive executable
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

## Verification status

Implemented and locally verified:

- deterministic urgency and summary unit tests;
- API import and route registration;
- Ruff formatting/lint and strict mypy for changed backend sources;
- web unit tests, lint, typecheck and production build;
- responsive, accessible loading, empty, error, personal and team states in code.

Pending before acceptance:

- disposable PostgreSQL integration coverage for the unified endpoint across two
  tenants and two units;
- authenticated browser visual regression for populated personal/team queues;
- real-user, keyboard and screen-reader acceptance;
- source-record deep linking to the exact selected record rather than only its module.
