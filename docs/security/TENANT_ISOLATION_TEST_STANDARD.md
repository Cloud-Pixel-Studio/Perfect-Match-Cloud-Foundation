# Tenant Isolation Test Standard

Tenant isolation is a release gate and runs as the distinct `tenant-isolation`
CI context against disposable PostgreSQL with forced RLS. Mock-only RLS tests
do not satisfy this gate.

The required matrix proves valid OIDC and active sessions, then denies invalid
signature, issuer, audience, expiry, nonce, state, state expiry/reuse, and PKCE;
missing, random, expired, and revoked sessions; missing or invalid CSRF; and
unauthorized tenant selection.

At the database layer User A may access only Tenant A, User B only Tenant B,
and Multi User both. Tenant A context must not select, insert, update, or delete
Tenant B rows. An intentionally unfiltered SELECT must still return only the
active context. A one-connection pool must clear context between transactions.
Membership revocation must remove access on the next request, and runtime role
elevation must fail.

Any cross-tenant result, authentication bypass, raw session-token persistence,
runtime superuser/BYPASSRLS status, or runtime ownership of tenant tables is an
automatic FAIL regardless of scanner severity.
