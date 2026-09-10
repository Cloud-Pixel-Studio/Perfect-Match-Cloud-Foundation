# Workflow Integrity Test Standard

The workflow suite must run against disposable PostgreSQL, not SQLite or mocks. It covers
tenant isolation, RLS with no tenant context, draft/published immutability, graph
reachability and cycle rules, active assignment eligibility, organization archive
protection, optimistic concurrency, append-only history, audit atomicity and rollback,
and terminal instance behavior. CI runs it in the separate `workflow-integrity` job.
