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
