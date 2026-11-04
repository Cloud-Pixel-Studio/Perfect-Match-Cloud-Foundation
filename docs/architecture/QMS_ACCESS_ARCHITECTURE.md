# Explicit QMS capabilities

Migration 0008 and `qms_access.py` establish business authorization independently
from commercial seats/ISO addons and from platform administration. This is a
foundation for future QMS domains, not the document control module itself.

## Scope and authority

- Every grant identifies one tenant, active member, exact organization unit and
  named capability. There is no wildcard, implicit parent inheritance or empty
  scope. Processes are not yet modeled by this change; unit scope does not
  establish process-level authorization parity with Odoo.
- Initial capabilities: documents read/author/review/approve/release, evidence
  read/create/review, and processes read/manage. A named capability is not proof
  its business module has been delivered.
- Only active tenant owners may create or revoke grants. Owners cannot grant
  capabilities to themselves. This is the initial conservative grant policy;
  any future delegation requires explicit design and negative tests.
- Owners/admins have no automatic business capability. A second authorized owner
  must explicitly grant a capability to an owner who needs to perform QMS work.
- Auditors may receive read capabilities only. Changing a member to auditor
  immediately disables existing write capabilities without rewriting history.
- User/membership/tenant disablement, unit archival and revocation are checked
  on each capability decision. Restoring a unit restores applicability of its
  still-active grants; revoke grants explicitly when access must remain removed.

## Persistence and API

`qms_access_grants` uses forced RLS, composite unit/tenant references and a unique
active grant per tenant/member/unit/capability. A grant's identity is immutable:
only an active-to-revoked change is accepted. Runtime DELETE/TRUNCATE are denied.
Revoking preserves the grant, original issuer and timestamps. Regranting creates
a new historical record.

The directory projection established by PMC-03 validates active target members
without granting the caller unrestricted access to membership/identity tables.
The SQL `qms_has_capability` helper runs as invoker, requires an active actor and
never elevates or bypasses RLS. Server domain handlers must establish context
from the authenticated session and call `require_capability` for the actual
record's scope; never trust a scope submitted solely to obtain authorization.

Endpoints:
- GET `/qms-access/grants`: own grants; tenant owners can inspect tenant grants;
  bounded to the newest 100 records. The owner management panel and personal
  read-only view use this endpoint; pagination beyond 100 is pending.
- POST `/qms-access/grants`: strict input, CSRF, tenant from authenticated session,
  owner authority and active scoped target validation.
- POST `/qms-access/grants/{id}/revoke`: CSRF, owner authority, tenant lookup,
  row lock and refreshed status. Repeated revocation returns conflict.

Creation/revocation and their typed audit event commit atomically. Audit failure
rolls back the grant. Audit payload contains safe IDs/capability/status, not file
contents or credentials. Constraint failures return generic conflict/denial
responses rather than disclosing SQL or foreign-tenant record details.

## Validation and limits

The disposable PostgreSQL suite covers explicit/empty scopes, forced RLS,
cross-tenant existing targets, no implicit owner authority, member escalation,
self-grants, invalid targets, duplicates, revocation, immutable history,
auditor restrictions, disabled identities/tenants, archived scope and audit
atomicity. Run `scripts/run-qms-access-integrity.sh`; CI and local checkpoint
include the suite. Its migration round-trip precedes tests; audit-bearing
downgrade is rejected by the transactional audit constraint restoration.

These controls do not yet enforce a document lifecycle: there is no document
module to call them. Document author/approver independence remains a separate
required domain rule. Process scopes, approval policies, commercial entitlements
and pagination beyond the initial bounded lists remain unfinished.

## Management interface

The authenticated shell shows owners a scoped grant form and a recent-history
table with explicit revoke/cancel confirmation. Other roles see only their own
grant list. Self-targets, inactive scopes and duplicate active grants are excluded
from the form; server checks remain authoritative. The UI does not label grants
as proof of effective access when a user, scope or membership is inactive.

Workspaces remount on tenant or role changes. Controls are disabled while the
organization context changes; cached audit rows are cleared and late responses
from the previous context are ignored. A mutation denied after a role/session
change clears stale rows and refreshes identity.

Browser validation used only local fictional data: owner login, create a named
development site, grant read access to pmc-user-a, reject duplicate creation,
cancel revocation, confirm revocation and retain history. A member/auditor could
not see management controls; switching tenants cleared the old organization data
and closed the prior audit panel. Test browser sessions were closed afterward.

A separate pmc-local-owner fixture exists only for development. The bootstrap
refuses missing, staging or production environment labels before contacting the
identity provider. Its generated password is outside Git; existing member test
users were not elevated. This is not a production onboarding mechanism.

## Related proxy correction

The web identity proxy previously accepted only alphabetic route segments,
rejecting UUID resource paths before reaching the API. It now accepts validated
UUIDs under known roots while rejecting traversal, embedded URLs, unknown roots
and excessive path depth. Resource authorization remains in the API; allowing
a syntactically valid identifier does not authorize that resource.
