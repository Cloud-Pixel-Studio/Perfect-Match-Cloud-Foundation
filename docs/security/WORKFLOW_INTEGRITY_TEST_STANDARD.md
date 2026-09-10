# Workflow Integrity Test Standard

The workflow suite runs against disposable PostgreSQL, never SQLite or mocks. The
collected matrix is **24 workflow-integrity cases** (the graph matrix contributes eight
parameterized cases) and runs in the separate `workflow-integrity` CI job.

The cases explicitly map to these controls:

- tenant isolation, forced RLS, and no-context visibility;
- published UPDATE, DELETE, and INSERT immutability for steps, transitions, and assignments;
- composite tenant/version identity for transitions, assignments, current steps, and events;
- pinned event references, append-only history, runtime DELETE denial, and bounded history API;
- audit records for step, transition, and assignment mutations, request correlation, and rollback on forced audit failure;
- owner/admin configuration and cancellation authority, member/auditor denial, active-user target lifecycle, and actor-specific eligible actions;
- required bounded cancellation reasons stored on the domain event;
- graph validation for no or multiple starts, missing end, unreachable steps, dead ends, outgoing end edges, cycles with exits, and cycles without exits;
- optimistic concurrency with two real PostgreSQL sessions, terminal behavior, and cross-tenant visibility.

The CI harness also verifies a clean `0004 -> 0005 -> 0004 -> 0005` migration cycle.
After workflow evidence exists, downgrade is expected to fail closed with SQLSTATE
`55000`; the workflow audit history is never deleted.
