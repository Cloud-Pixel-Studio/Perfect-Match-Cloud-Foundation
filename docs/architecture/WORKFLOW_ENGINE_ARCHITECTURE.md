# Workflow Engine Architecture

PMC-04 adds a tenant-scoped, versioned workflow state machine to Perfect Match Cloud.
Definitions and draft versions are editable only by tenant owners and administrators. A
published version is a permanent snapshot: its steps, transitions, and assignments cannot
be updated or deleted, and a new draft version is required for changes.

## State machine

Each version has exactly one start step, one or more end steps, and typed task, approval,
or end steps. Publication validates start uniqueness, reachability, dead ends, end-step
outgoing edges, assignment targets, and that every path can reach an end. Cycles are
allowed only when a path exits the cycle to an end. Transitions are explicit rows; no
expressions, scripts, eval, webhooks, email, or external automation execute.

Instances pin a published version at start. Every transition locks the instance row,
checks the caller's expected `row_version`, verifies the current step and assignment,
increments the version, and appends domain history in one transaction. Owners and admins
do not receive an implicit transition bypass. Completion and cancellation are terminal.

Assignments target an active user, active organization unit membership, or application
role (`owner`, `admin`, or `member`). Disabled users, revoked memberships, and archived
units cannot satisfy an assignment. Organization lead assignments never escalate into
application-owner or administrator authority.

## Isolation and evidence

Every workflow table has enabled and forced PostgreSQL RLS. Runtime access requires the
transaction-local `app.tenant_id` and an active membership; the runtime role has no
`BYPASSRLS`, and delete privileges are absent. Workflow history and audit events are
append-only. Workflow audit records are emitted only by `audit_service`, with a fixed
action/resource contract, request ID correlation, and the domain mutation plus audit row
committed atomically.

The organization archive guard also rejects archiving a unit with active workflow work.
The API exposes definitions, versions, builder records, publication, instances,
transitions, cancellation, and read-only history without a delete endpoint.

## Delivery controls

The dedicated `workflow-integrity` CI job provisions disposable PostgreSQL and runs the
real integrity suite. The required check is added to the protected ruleset only after a
successful PMC-04 pull request run. The UI is a keyboard-accessible, responsive builder
with explicit forms and read-only views for auditors and members. PMC-04 does not start
PMC-05 or create releases/tags.
