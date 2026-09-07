# Session Security

Successful OIDC authentication always creates a new Perfect Match session. The
browser receives an opaque token generated from 32 random bytes (256 bits); the
database stores only its SHA-256 digest. The cookie is host-only, HttpOnly,
`Path=/`, and `SameSite=Lax`. Production startup refuses `Secure=false`; local
HTTP development is the only approved insecure-cookie mode.

OIDC authorization uses a separate 256-bit transient login binding. Its raw
value exists only in an HttpOnly, `SameSite=Lax`, `/auth` cookie for at most the
login transaction TTL; PostgreSQL stores only its SHA-256 digest. It is never an
application session credential and is cleared after a successful callback.

Sessions have server-side expiry, last-seen, revocation, user, and optional
current-tenant state. Missing, random, expired, revoked, and disabled-user
sessions deny access. Logout revokes the record before clearing both cookies.
PostgreSQL also rejects any runtime insert or update that sets
`current_tenant_id` without an active membership for the session user.

Mutating POST, PUT, PATCH, and DELETE operations require a separate random,
session-bound CSRF token in both cookie and `X-CSRF-Token`. The server compares
only token hashes using constant-time comparison and additionally validates an
Origin header when present. SameSite is defense-in-depth, not the CSRF control.
