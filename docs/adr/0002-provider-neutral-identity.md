# ADR 0002: Provider-Neutral Identity Boundary

Status: Accepted for PMC-01

## Decision

Perfect Match accepts standards-compliant OpenID Connect providers through a
small application-owned OIDC boundary. Authentication uses discovery,
Authorization Code flow, PKCE S256, nonce, one-time state, restricted signing
algorithms, and issuer, signature, audience, expiry, and nonce validation. The
validated external identity key is `issuer + subject`; email is profile data,
not identity.

After validation, Perfect Match creates a new opaque local server-side session.
Business and tenancy code consumes only the authenticated local user and a
server-validated tenant context. It never consumes Keycloak APIs or upstream
access tokens.

## Local provider

Keycloak 26.7.3 is local development infrastructure only. Its official
Apache-2.0 image is pinned as
`quay.io/keycloak/keycloak:26.7.3@sha256:ff4257d0d64efbe99ed1ddfaf07765cc3c36dc7518bf8324d41961327f441c54`.
The isolated local bootstrap module is the only Keycloak-specific code.

## Consequences

AWS Cognito, Microsoft Entra ID, Okta, Ping, or another standards-compliant
OIDC provider can replace Keycloak by configuration and interoperability
validation. Production provider contracts, SAML, SCIM, and provisioning remain
deferred. No AWS resource is created by this decision.
