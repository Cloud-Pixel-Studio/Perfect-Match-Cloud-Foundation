# Production public URL validation — scoped defense in depth

The production settings guard rejects insecure or malformed **public** URL configuration before the FastAPI process is ready. This is an incremental P0 misconfiguration control, not proof of production readiness.

## Validated on `PMC_ENVIRONMENT=production`

- `PMC_COOKIE_SECURE=true` and a non-empty login transaction key remain mandatory.
- `PMC_WEB_URL`, `PMC_OIDC_ISSUER` and `PMC_OIDC_CALLBACK_URL` must use HTTPS.
- These public URLs must not contain embedded credentials, query strings or fragments; malformed ports are rejected.
- `PMC_WEB_URL` must be an origin, not a path, so it can serve as an exact CORS/origin check.
- Development loopback defaults are unaffected when `PMC_ENVIRONMENT=development`.

Private backchannel/discovery URLs and S3 endpoints are intentionally not altered in this change. Their production transport requirements, trusted network boundaries, external OIDC provider, domain names and credentials must be decided in a separate production architecture review. The local Keycloak `start-dev` and synthetic seed process remain development-only.

## Evidence

`apps/api/tests/test_production_public_urls.py` covers accepted HTTPS origins, HTTP rejection for each public field, userinfo, fragments, queries, malformed ports, frontend origin paths and backward-compatible development defaults. The tests run in the backend quality job.

## Additional release blockers

This change does not remediate third-party image High/Critical advisories or replace missing MFA, secrets management, backup/restore, tenant-scoped object storage tests, authenticated DAST, monitoring or a production deployment profile. Current release security gate must remain fail-closed until all material blockers are resolved.
