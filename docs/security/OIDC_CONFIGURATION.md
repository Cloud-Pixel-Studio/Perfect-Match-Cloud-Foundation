# OIDC Configuration

The runtime configuration provides issuer, discovery URL, optional container
backchannel base URL, public client ID, callback URL, and web origin. Discovery
must return the configured issuer and authorization, token, and JWKS endpoints.

The local client is public and uses Authorization Code flow with PKCE S256.
Implicit flow, Direct Access Grant, service accounts, and client secrets are
disabled. Login transactions store only state and browser-binding digests, an
encrypted PKCE verifier, nonce, timestamps, expiry, and one-time use marker. A
32-byte random binding is held only in the short-lived, HttpOnly, `SameSite=Lax`
`pm_login` cookie scoped to `/auth`. The callback validates both state and the
binding before consuming the transaction, preventing login CSRF and
cross-browser session swapping. Success clears the transient cookie.

The single binding cookie intentionally permits one outstanding login per
browser. Starting another login replaces the binding for the earlier attempt;
the earlier callback then fails. Supporting concurrent login tabs would require
a separately reviewed multi-transaction cookie design.

ID tokens accept only RS256, PS256, or ES256 and require valid signature,
issuer, subject, expiration, and nonce. Audience is strict: `aud` must contain
exactly the configured Perfect Match client ID, with no additional audience. If
`azp` is present, it must equal that same client ID. Discovery metadata that
advertises PKCE methods must include `S256`; Perfect Match never falls back to
plain PKCE. Local Keycloak independently requires S256. Perfect Match does not
expose a password form and never receives user passwords.
