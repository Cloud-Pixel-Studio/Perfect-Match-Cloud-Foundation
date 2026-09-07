# PMC-01 Security Assessment

Assessment date: 2026-09-06

This assessment records the final local-development scan triage for PMC-01. It does not suppress scanner output or approve any image for production deployment.

## Cleared gates

- Repository filesystem: zero Trivy vulnerability, secret, or failed misconfiguration findings.
- API image: zero Trivy findings after upgrading Alpine packages and pinning Cryptography 50.0.1.
- Web image: zero Trivy findings.
- Python and Node dependency audits: no known vulnerabilities after remediation.
- OpenGrep: zero findings across application sources; all committed custom-rule fixtures pass.
- Gitleaks: no findings in the worktree or repository history.

## Upstream image triage

| Image | Raw Trivy result | Reachability decision |
| --- | --- | --- |
| Keycloak 26.7.3 | 2 high, 10 medium, 22 low | Not confirmed in the local profile. The SQL Server JDBC driver is not loaded because local Keycloak uses its embedded development database. The JDK libpng path does not process attacker-supplied images. |
| PostgreSQL 18 Alpine | 1 critical, 30 high, 28 medium, 14 low, 11 unknown | Not confirmed in the local profile. Twenty-two critical/high records belong to the startup-only `gosu` binary; it performs a local UID/GID transition and does not invoke the affected TLS, HTTP, mail, URL, template, XML, or certificate paths. Seven `libuuid` records describe mount/nsenter tools that are absent from the image. The OpenSSL record concerns QUIC server handling, which PostgreSQL does not use. The newer canonical tag digest was also scanned and had the same profile. |
| SeaweedFS 4.45 | 2 high, 23 unknown | Not confirmed in the local profile. The affected Thrift service and image-decoding/thumbnail paths are not enabled by the S3-only development command. The endpoint remains loopback-bound and authenticated. |

The currently pinned Keycloak and SeaweedFS tags are the latest canonical releases reviewed for this checkpoint. These findings are accepted only for isolated local development. Production selection requires a fresh scan and separate authorization.

## Known web finding

The existing medium CSP item, `script-src 'unsafe-inline'`, remains documented. PMC-01 did not broaden it. Browser-to-API identity traffic uses the constrained same-origin `/api/identity` proxy so `connect-src 'self'` remains intact.

## Gate decision

- Critical unresolved and reachable: 0
- High confirmed unresolved and reachable: 0
- Cross-tenant findings: 0
- Authentication bypass findings: 0
- Session-secret findings: 0

Tenant-isolation failure, authentication bypass, session-token exposure, or a privileged runtime database role remains an automatic failure regardless of scanner triage.
