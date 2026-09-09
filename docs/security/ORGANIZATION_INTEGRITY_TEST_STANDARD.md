# Organization Integrity Test Standard

The PMC-03.1 integrity gate uses disposable PostgreSQL with the migration chain
at `0004_organization_structure`. Before the tests, it proves a clean
`0003 -> 0004 -> 0003 -> 0004` migration cycle. It verifies same-tenant
hierarchy, real Tenant B parent isolation, self-parent and cycle rejection,
archived-parent rules, case-insensitive code uniqueness, archive dependency
blocking, active membership requirements, archived-unit assignment creation
and reactivation rejection, primary assignment uniqueness, and real
cross-tenant assignment and assignment-ID denial.

The suite verifies that the former target-user GUC pattern cannot read
Membership rows without actor context, that revoked actors are denied, and
that the narrow member-directory projection returns only `id`, `display_name`,
and application `role` for active members of the current tenant. It preserves
`memberships_self` and `users_self`; it does not expose email, identity
provider, credential, or session fields. Assignment display names use the same
validated projection.

It also verifies owner/admin write access, member/auditor denial,
active-role reads, forced RLS, runtime no-delete behavior, pooled context
reset, and that a lead assignment does not change application membership
authorization. The actual Organization Service mutation plus audit success is
committed atomically; forced audit failure rolls it back, constraint failure
creates no audit event, request IDs are preserved, and unsupported audit
payload fields are rejected. Downgrade fails closed when organization audit
history exists and never deletes historical events.
