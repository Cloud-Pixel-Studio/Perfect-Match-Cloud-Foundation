# Security Testing Standard

Focused checks run during implementation; the complete gate runs at checkpoint.
The baseline includes OpenGrep SAST, custom rule fixtures, Trivy vulnerability,
secret, misconfiguration and image scans, Gitleaks worktree and history scans,
Python and Node dependency audits, license validation, CycloneDX SBOM generation,
and passive OWASP ZAP baseline scanning against only the disposable local app.

Future security tests must prove cross-tenant read, update, and delete denial;
self-role-elevation denial; expired and modified token rejection; immutable audit
events; private storage URLs; and cross-tenant AI retrieval prevention.

Active attack scanning, production targeting, LAN discovery, and external source
upload are prohibited in PMC-00.

## Current browser boundary

The shell uses a fresh cryptographic CSP nonce per request, dynamic rendering
and private/no-store document responses. Production scripts do not use
`unsafe-inline` or `unsafe-eval`. Incoming nonce/CSP headers are replaced.
The local HTTP environment does not establish production TLS/HSTS readiness.

ZAP rule 10109 is retained in the report and classified as the informational
Modern Web Application observation. It is not suppressed as a vulnerability;
the final evidence manifest records its title, risk, confidence, and count.

ZAP rule 10049 is retained as an informational cacheability observation. The
UI uses explicit cache policies: authenticated documents are private/no-store,
while versioned static assets may be cached. Inspect the affected URL and content
before accepting any cache observation.

The web boundary sets COOP same-origin, COEP require-corp and CORP same-origin.
Revalidate these policies when external resources, embedding or popup identity
flows are introduced. Local OIDC uses top-level navigation.

## Third-party image gate

Trivy reports for PostgreSQL, Keycloak and SeaweedFS must contain a Results array.
CI fails on HIGH or CRITICAL vulnerabilities, matching the application-image
gate. A newer image tag alone is not evidence of remediation. Do not suppress
findings to satisfy the gate; record applicability, fixes and release blockers
with the image digest and scanner database date.
