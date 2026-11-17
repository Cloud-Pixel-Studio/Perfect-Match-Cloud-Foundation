# Active-company boundary

This change addresses finding A01 from PR40. It does not change who may approve,
review or manage an active company's QMS records. Other findings from that audit
remain separate, including the broad intratenant directory/audit/workflow read
policies, the management limit of 100 grants and publication with an auditor-only task.

## Behavior

Business context now requires one currently active company, active user and active
membership. Organization, Workflows, QMS actor context and the audit-event reader
use one scalar database query rather than cached ORM attributes. Grant creation
and revocation also refresh the supplied service actor, preserving 403 for an
inactive actor and preventing a stale role snapshot from authorizing a command.

Authentication remains separate. A valid user whose selected company is disabled
can still inspect their identity, list other authorized active companies, select
another one and log out. No role, seat, grant or company is provisioned by this
fix. `/tenant/context` retains its existing behavior of clearing a revoked
selection. A tenant-scoped business endpoint rejects inactive context with 403;
a missing selection remains 409.

Successful audit-event responses additionally declare `Cache-Control: private,
no-store`. The existing role allow-list and append-only event history remain
unchanged; this does not implement a unit-scoped audit-reading capability.

## PostgreSQL enforcement

Migration `0049_tenant_suspension` follows 0048. It adds a restrictive policy for
all commands by `pmcloud_app` to these 11 older tables:

- `tenant_isolation_probes`;
- `organization_units`, `organization_unit_assignments`;
- `workflow_definitions`, `workflow_versions`, `workflow_steps`,
  `workflow_transitions`, `workflow_step_assignments`, `workflow_instances`,
  `workflow_instance_events`;
- `audit_events`.

Each policy requires the exact selected tenant and the existing invoker helper
`qms_access_actor_is_active()`, which joins active membership, user and tenant.
Existing QMS domain policies already use that helper or `qms_has_capability()`.
The new policies narrow the old rules without replacing their role, assignment,
capability or scope checks. PostgreSQL combines restrictive policies with AND;
they cannot themselves grant access. See the
[PostgreSQL CREATE POLICY documentation](https://www.postgresql.org/docs/current/sql-createpolicy.html).

The existing `organization_member_directory()` definer function also checks the
active-actor helper before exposing its private projection. The existing
`lock_qms_site_scope(uuid,uuid)` definer function checks the same helper before
consulting or locking its private projection, rejecting inactive context with SQLSTATE 42501.
Both are replaced in place, preserving their existing owners and execute ACLs.
No new definer function, runtime SQL privilege, role or capability is introduced.
Other private getters remain guarded by their existing active-capability checks.

Identity and session tables retain their existing RLS. In particular, a member
must still be able to recover their context after one company is suspended.
Direct identity access remains confined to the already authorized user/session;
it is not an exception granting business data from a disabled company.

## Transaction and restoration limits

Application sessions use PostgreSQL READ COMMITTED. A committed status change
is observed by subsequent statements; this does not cancel already running
queries, retract data already loaded into a response or terminate work already
executed before suspension. This patch does not claim linearizable revocation
across arbitrary long-running or repeatable-read transactions. A worker must
establish fresh request context and revalidate authorization for its command.

Downgrade refuses with SQLSTATE 55000 while any disabled company exists. Because the migration
owner is NOBYPASSRLS, the check temporarily removes FORCE from `tenants` inside
the migration transaction, obtains owner visibility and restores FORCE. The DDL
lock serializes status changes until transaction end. A rejected downgrade rolls
back this flag change and retains all policies and function bodies. Runtime
cannot perform this DDL. An allowed downgrade removes no business records or
append-only history and restores both previous function bodies.

The previously unactivated lifecycle proposal in the Design Studio worktree
used 0049 only as a planned number. It was not copied into this branch or enabled.
Its eventual migration must follow this security revision under a fresh ID; no
execution/readiness feature is delivered by this change.

## Verification and operations

Implemented and verified in disposable PostgreSQL: 31 focused cases PASS; 11 deliberately failing old-schema read cases demonstrate the prior SQL gap. Existing suites add 418 distinct integration cases (199 process/CAPA, 121 audits, 23 access, 31 workflow, 17 organization, 27 isolation), for 449 distinct integration cases total. API unit tests 50 PASS; the default run separately skips 449 integration cases without the harness. Format/Ruff/mypy on 73 files, ShellCheck, scoped OpenGrep (6 rules / 6 files) and secret scans/checksum negative controls PASS. No dependencies or locks changed.

Initial validation found one regression: the tightened directory caused a disabled grant issuer to receive 409 rather than 403. Revalidating the grant service actor fixed the classification without changing the old test. Two focused fixture failures used an invalid membership status and were corrected to revoked. Later Docker disk exhaustion interrupted disposable container startup; a bounded RAM filesystem in the test harness allowed all 31 cases and the old-schema negative controls to complete. These environment/fixture failures are distinct from the fixed product regression.

The local development database remains 0048 and the existing API stays healthy. No development-schema migration or frontend image change was applied because Docker storage is exhausted. The new migration is tested in isolated databases and prepared for review, not claimed deployed. A separate encrypted backup of the actual 0048 database was restored successfully (57 tables, 50 forced RLS). Full browser/visual regression and a new dependency vulnerability scan were not run for this backend-only patch; exact-head CI remains a separate gate.
The focused regression harness uses disposable PostgreSQL and synthetic HTTP
sessions, not real users or Keycloak credentials. It covers API/SQL denial,
directory and site-lock behavior, reactivation without new grants, company
switching/logout, actor disablement, current snapshots and migration rollback.
Other domain harnesses check existing behavior for active companies.

Before touching the development schema, preserve and restore a separate encrypted
database checkpoint. Production is not a target of this work. The source baseline
and prior lifecycle WIP are backed up independently outside the working tree;
restoration proofs and verification status must be distinguished from test PASS.

## Review delivery

[Draft PR41](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/41) is stacked on PR40. Functional commit `b0f7de816ef7775793e63f3047ef34f279d9ad58`, tree `3b11961c91b19510e9a593f38bec17250c66a3b4`, matches the verified local tree exactly. Local Git metadata was preserved by a checkpoint tag before aligning the branch to GitHub's commit metadata. The final continuity update follows that functional commit; it changes documentation only. Human review and exact-head CI remain required before merge. No production or local schema upgrade is claimed.
