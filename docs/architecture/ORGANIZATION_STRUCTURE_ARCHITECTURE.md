# Organization Structure Architecture

PMC-03 adds tenant-scoped product organization structure. `organization_units`
uses an adjacency-list hierarchy rooted directly at the existing tenant. The
bounded unit types are `site`, `department`, and `team`; codes are unique
case-insensitively within a tenant. Composite tenant keys, database triggers,
and service validation prevent cross-tenant parents, self-parenting, cycles,
and active children below archived parents.

`organization_unit_assignments` associates a tenant member with one or more
units as `member` or `lead`. An active user has at most one primary assignment
per tenant. An assignment is structural metadata only: it never changes or
grants `Membership.role`, so a unit lead is not an application administrator.
Assignments require an active membership and an active unit. Units and
assignments are archived/inactivated for traceability; runtime hard delete is
not granted and no delete API exists.

Both tables use enabled and forced PostgreSQL RLS. Active tenant membership is
required for reads; owner and admin membership is required for writes. The API
derives tenant context from the validated PMC-01 session and never accepts a
client-selected tenant ID for organization operations. Lists are bounded to
100 rows per request with deterministic ordering.

Successful organization mutations call typed builders in the single PMC-02
audit service. The business mutation and audit append share the request
transaction and server-generated request ID; an audit failure rolls back the
business mutation. Payloads contain only safe organization fields and remain
subject to the forbidden-key validator.

The Organization screen provides a keyboard-operable hierarchy, search,
selected-unit details, assignment visibility, responsive layouts, and explicit
read-only behavior for members and auditors. It distinguishes organization
lead/member from application owner/admin/auditor/member roles.

The `organization-integrity` CI gate exercises PostgreSQL hierarchy, tenant
isolation, membership, assignment, authorization, RLS, no-delete, audit
atomicity, and connection-context behavior. PMC-04 may later consume units and
assignments for workflow targeting; PMC-04 is not implemented here.
