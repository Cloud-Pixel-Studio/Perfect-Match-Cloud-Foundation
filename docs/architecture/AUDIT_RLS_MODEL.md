# Audit RLS Model

`audit_events` has enabled and forced RLS. An insert must match the transaction tenant and authenticated user, an active membership, the active membership role, and the authenticated user's current display name. Readers must match the transaction tenant and hold owner, admin, or auditor membership. Members and missing, invalid, or revoked contexts cannot read or append. Every query is tenant scoped and ordered by occurred time and UUID.
