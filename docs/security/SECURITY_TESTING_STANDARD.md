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

## PMC-00 baseline risk treatments

ZAP rule 10055 remains `WARN`: Next.js hydration uses inline bootstrap scripts.
The local shell's CSP otherwise limits scripts, connections, images, forms,
frames, and objects to explicit safe sources. This exception is limited to the
disposable foundation UI, which renders no customer or user-authored content.
Nonce-based script policy is required before production exposure.

ZAP rule 10109 is ignored because it only classifies the target as a modern web
application. It is not a vulnerability. The suppression is scoped to the
PMC-00 local passive baseline configuration.
