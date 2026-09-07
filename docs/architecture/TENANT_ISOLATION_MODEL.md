# Tenant Isolation Model

A browser may request a tenant identifier only as a selector. The server loads
the opaque application session, identifies the local user, verifies an active
membership, and only then stores `current_tenant_id`. Tenant routes derive
context from that server-side session and recheck active membership on access.

Tenant, User, ExternalIdentity, Membership, ApplicationSession, and
OIDCLoginTransaction form the minimum identity domain. Membership roles are
limited to `owner`, `admin`, `member`, and `auditor`; PMC-01 does not implement
the final permission engine or membership-administration endpoints.

The runtime role has no membership write privilege. Revocation by a privileged
bootstrap/migration context takes effect on the next request even when an
application session remains active. Synthetic Tenant A, Tenant B, User A, User
B, and Multi User data is restricted to local and test bootstrap paths.
