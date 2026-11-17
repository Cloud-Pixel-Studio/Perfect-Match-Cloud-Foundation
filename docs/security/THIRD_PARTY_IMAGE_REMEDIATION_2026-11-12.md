# Third-party container remediation — 2026-11-12

Evidence: Foundation security run [43152575972](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/43152575972), commit `9e91a245ab2603a01316706a13a354c8061ae5fa`, artifact `foundation-security-evidence-9e91a245ab2603a01316706a13a354c8061ae5fa`. The Trivy report is a point-in-time finding; re-scan before making release decisions.

## Blocking findings (HIGH)

| Image | Vulnerability | Package | Installed | Fixed version in scanner |
| --- | --- | --- | --- | --- |
| Keycloak 26.8.1 | CVE-2026-91403 | java-21-openjdk-headless | 1:21.0.12.1.1-1.2.el9 | Not reported |
| Keycloak 26.8.1 | CVE-2026-91415 | java-21-openjdk-headless | 1:21.0.12.1.1-1.2.el9 | 1:21.0.13.0.9-1.2.el9 |
| Keycloak 26.8.1 | CVE-2026-119373 | sqlite-libs | 3.34.1-11.el9_8 | Not reported |
| Keycloak 26.8.1 | CVE-2026-119374 | sqlite-libs | 3.34.1-11.el9_8 | Not reported |
| Keycloak 26.8.1 | CVE-2026-119379 | sqlite-libs | 3.34.1-11.el9_8 | Not reported |
| Keycloak 26.8.1 | CVE-2026-119586 | sqlite-libs | 3.34.1-11.el9_8 | Not reported |
| Keycloak 26.8.1 | CVE-2026-102554 | com.google.guava:guava | 33.6.0-jre | 33.7.2 |
| SeaweedFS 4.51 | CVE-2026-116587 | github.com/go-jose/go-jose/v4 | v4.1.5 | 4.1.6 |
| SeaweedFS 4.51 | CVE-2026-78661 | golang.org/x/net | v0.61.0 | 0.62.0 |

Other third-party images: PostgreSQL 0, ClamAV 0 HIGH/CRITICAL findings. Application images: API 0, web 0 HIGH/CRITICAL findings. These are scanner observations, not a claim of absence of all vulnerabilities.

## Remediation order and verification

1. Check vendor-published Keycloak and SeaweedFS releases for patched image digests; **do not change tags without verifying the digest and re-scanning**. Confirm whether the Go and Java transitive dependencies are included in the rebuilt image.
2. For Keycloak, verify the Java/OpenJDK update and Guava version in the candidate image; investigate SQLite advisories lacking a scanner-supplied fix with upstream distro/vendor security bulletins. Do not presume that a new tag resolves every CVE.
3. For SeaweedFS, verify the candidate binary includes `go-jose/v4 >= 4.1.6` and `golang.org/x/net >= 0.62.0`; a patched container OS alone is insufficient.
4. Update both `docker-compose.yml` and the matching image scan targets in `.github/workflows/security.yml` in the **same PR**. Keep digest pinning; do not loosen the severity gate.
5. Require a green full Foundation security workflow, quality workflow, CodeQL, identity/authentication E2E, S3 document isolation and backup/restore checks before merging or deploying.
6. If no patched vendor release exists, keep production blocked and track the upstream fix; do not suppress CVEs or claim release readiness.

This document is a remediation record, **not** a vulnerability waiver or security approval.
