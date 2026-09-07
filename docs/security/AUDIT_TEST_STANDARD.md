# Audit Test Standard

Audit-integrity validation must use disposable PostgreSQL and exercise tenant A/B reads and inserts, forced-RLS context, actor user/role/display-name forgery, immutable update/delete, reader roles, missing and revoked context, pool reset, secret minimization, request correlation, bounded cursor pagination, and atomic business-plus-audit success and rollback. Synthetic secrets are used only in tests. A failing append must prove the business mutation is absent.
