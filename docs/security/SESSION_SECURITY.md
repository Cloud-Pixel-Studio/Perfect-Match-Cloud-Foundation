# Session Security

Successful OIDC authentication always creates a new Perfect Match session. The
browser receives an opaque token generated from 32 random bytes (256 bits); the
database stores only its SHA-256 digest. The cookie is host-only, HttpOnly,
`Path=/`, and `SameSite=Lax`. Production startup refuses `Secure=false`; local
HTTP development is the only approved insecure-cookie mode.

Sessions have server-side expiry, last-seen, revocation, user, and optional
current-tenant state. Missing, random, expired, revoked, and disabled-user
sessions deny access. Logout revokes the record before clearing both cookies.

Mutating POST, PUT, PATCH, and DELETE operations require a separate random,
session-bound CSRF token in both cookie and `X-CSRF-Token`. The server compares
only token hashes using constant-time comparison and additionally validates an
Origin header when present. SameSite is defense-in-depth, not the CSRF control.
