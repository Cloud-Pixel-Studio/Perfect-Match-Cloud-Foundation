# Identity Architecture

The authentication chain is:

`OIDC provider -> Perfect Match OIDC boundary -> local application session -> authenticated user -> validated tenant context`

The boundary discovers provider metadata, redirects with Authorization Code and
PKCE S256, exchanges the one-time code, validates the ID token, and maps
`issuer + subject` to a local user. It does not process passwords. Upstream
tokens are not placed in browser storage and are discarded after identity
validation.

The authorization transaction is bound to its initiating browser with an
independent random cookie whose digest is stored beside state. State alone is
therefore insufficient to complete a callback in another browser. The OIDC
boundary also requires one exact client audience and validates `azp` whenever
the provider supplies it.

Keycloak supplies the local OIDC protocol endpoint, but no business module
imports a Keycloak SDK or calls a Keycloak business API. The backchannel base
URL setting only handles container networking when a provider publishes a
browser-facing issuer. Provider metadata remains authoritative.

Future AWS deployment may map the same boundary to Cognito, database execution
to RDS PostgreSQL, runtime secrets to Secrets Manager, and containers to a
managed runtime. These are conceptual portability mappings only; PMC-01 creates
no AWS resources.
