# Tenant Isolation Test Standard

Tenant isolation is a release gate and runs as the distinct `tenant-isolation`
CI context against disposable PostgreSQL with forced RLS. Mock-only RLS tests
do not satisfy this gate.

The required matrix proves valid OIDC and active sessions, then denies invalid
signature, issuer, audience, expiry, nonce, state, state expiry/reuse, and PKCE;
missing, random, expired, and revoked sessions; missing or invalid CSRF; and
unauthorized tenant selection.

Login tests bind state to the initiating browser's transient cookie. A callback
from a second browser, a missing or wrong binding, an expired transaction, and
state replay must fail without issuing a session. The suite verifies that only
the binding digest is stored. OIDC claim tests accept one exact audience, reject
unknown additional audiences, and require any `azp` value to match the client.

At the database layer User A may access only Tenant A, User B only Tenant B,
and Multi User both. Tenant A context must not select, insert, update, or delete
Tenant B rows. An intentionally unfiltered SELECT must still return only the
active context. A one-connection pool must clear context between transactions.
Membership revocation must remove access on the next request, and runtime role
elevation must fail. Direct runtime-role tests must also reject setting a
session's current tenant to another or revoked tenant while accepting active
memberships for the single-tenant and multi-tenant fixtures.

Any cross-tenant result, authentication bypass, raw session-token persistence,
runtime superuser/BYPASSRLS status, or runtime ownership of tenant tables is an
automatic FAIL regardless of scanner severity.
