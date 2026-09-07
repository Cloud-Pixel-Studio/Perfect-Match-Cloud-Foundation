# Local Identity Provider

Keycloak 26.7.3 is used only as a disposable local OIDC provider.

| Evidence | Value |
| --- | --- |
| Canonical project | https://www.keycloak.org/ |
| Canonical source | https://github.com/keycloak/keycloak |
| License | Apache-2.0 |
| Image | `quay.io/keycloak/keycloak:26.7.3` |
| Digest | `sha256:ff4257d0d64efbe99ed1ddfaf07765cc3c36dc7518bf8324d41961327f441c54` |

The endpoint binds to host loopback only and the container is capped at 768 MiB.
An idempotent infrastructure bootstrap creates the `perfect-match` realm, a
public PKCE client, and neutral `pmc-user-a`, `pmc-user-b`, and
`pmc-multi-user` identities. Passwords and the bootstrap administrator
credential are generated in `~/.config/pmcloud/dev.env`, never committed or
displayed by the product.

Keycloak is not a Perfect Match product dependency. Replacing it with any
standards-compliant OIDC provider does not change the local session, user,
membership, tenant context, or RLS model.
