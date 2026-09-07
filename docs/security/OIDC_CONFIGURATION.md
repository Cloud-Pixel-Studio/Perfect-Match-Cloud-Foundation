# OIDC Configuration

The runtime configuration provides issuer, discovery URL, optional container
backchannel base URL, public client ID, callback URL, and web origin. Discovery
must return the configured issuer and authorization, token, and JWKS endpoints.

The local client is public and uses Authorization Code flow with PKCE S256.
Implicit flow, Direct Access Grant, service accounts, and client secrets are
disabled. Login transactions store only a state digest, an encrypted PKCE
verifier, nonce, timestamps, expiry, and one-time use marker. State is consumed
before code exchange so a failed exchange cannot be replayed.

ID tokens accept only RS256, PS256, or ES256 and require valid signature,
issuer, subject, audience, expiration, and nonce. Perfect Match does not expose
a password form and never receives user passwords.
