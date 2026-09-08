# Organization Integrity Test Standard

The PMC-03 integrity suite uses disposable PostgreSQL with the migration chain
at `0004_organization_structure`. It verifies same-tenant hierarchy, composite
tenant parent isolation, self-parent and cycle rejection, archived-parent
rules, case-insensitive code uniqueness, archive dependency blocking, active
membership requirements, archived-unit assignment rejection, primary
assignment uniqueness, and cross-tenant assignment denial.

The suite also verifies owner/admin write access, member/auditor denial,
active-role reads, forced RLS, runtime no-delete behavior, pooled context
reset, and that unit leads cannot change application membership roles. Business
mutation plus audit success is committed atomically; an audit failure rolls it
back, and a failed organization mutation creates no audit event.
