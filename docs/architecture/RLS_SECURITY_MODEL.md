# RLS Security Model

The PostgreSQL bootstrap identity creates roles only. The migration identity
owns schema objects and executes Alembic. The `pmcloud_app` runtime identity is
LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, and NOBYPASSRLS;
it owns no tenant table and has no `SET ROLE` path.

RLS is enabled and forced on users, external identities, memberships, tenants,
application sessions, login transactions, and the disposable tenant-isolation
probe. Runtime access is limited by grants and policies. Membership rows are
readable only for the current user, tenant rows require active membership, and
tenant-scoped DML requires both matching user membership and tenant context.

The database boundary sets `app.user_id`, `app.tenant_id`, session hash, and
OIDC lookup values with `set_config(..., true)`. The final `true` makes values
transaction-local, so pool return or rollback clears context. Every future
tenant-scoped table must:

1. contain a non-null tenant foreign key;
2. be owned by the migration role, never the runtime role;
3. enable and force RLS;
4. grant only required DML to the runtime role;
5. use both `USING` and `WITH CHECK` policies tied to transaction-local context;
6. prove unfiltered SELECT and cross-tenant INSERT, UPDATE, and DELETE denial.
