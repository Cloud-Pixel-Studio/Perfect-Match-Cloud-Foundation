# Architecture audit — 2026-11-02

## Repository state

The official remote is `Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation`.
`origin/main` is `889a5f1`; local HEAD is `e2cdff8`, ten commits ahead and equal to
open PR #12. The worktree contains 37 modified and 130 untracked paths. Most QMS
work—migrations 0006–0039, backend modules, UI, tests and documents—is local only.
GitHub must not be treated as a complete representation of the product.

CP-00 preserved and restored the source, Git history and PostgreSQL database before
this audit. The database is at migration 0038 while source reaches 0039.

## Architecture decision

Keep the modular monolith: Next.js/React/TypeScript, FastAPI/Python,
SQLAlchemy/Alembic/PostgreSQL, provider-neutral OIDC, private S3-compatible storage,
ClamAV, Docker Compose and GitHub Actions. It preserves existing identity, RLS,
auditing and QMS workflow controls. No evidence supports a rewrite, Odoo dependency
or premature microservice split.

## Functional status

Working with substantial automated evidence: identity, tenant isolation, technical
audit, organization, workflow, unit-scoped QMS grants, processes, document control,
controls/activities/evidence, risks, NCR and CAPA through 0038. Direct CAPA links in
0039 pass disposable PostgreSQL tests but are not applied to the preserved runtime.

Partial: dashboard, core QMS, implementation guidance, documents, risks, NCR, CAPA
and methodology pack. Missing: internal audit, calibration, cost of quality,
customer/supplier quality, KPI, management review, competence/training, action
center, migration/import, ISO edition packs and the commercial subscription/seat/
entitlement platform. No complete Odoo parity has been accepted.

## Priority debt

1. Preserve and review the 130 untracked paths through a dedicated PR strategy.
2. Align source and database at 0039, then repeat OIDC/proxy/runtime evidence.
3. Resolve dependency and container release blockers before product work expands.
4. Add production TLS/MFA, backup automation, RPO/RTO, observability and incident response.
5. Build subscriptions, seats and ISO entitlements independently from user authority.
6. Split oversized modules incrementally behind existing contracts; do not rewrite.
7. Replace stale README/status text and complete option-level Odoo comparison.

See `docs/security/SECURITY_AUDIT_2026-11-02.md` and
`docs/product/ODOO_FUNCTIONAL_PARITY_MATRIX.md` for security and functional detail.
