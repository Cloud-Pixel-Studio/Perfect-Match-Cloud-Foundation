# CI Supply-Chain Governance

Perfect Match Cloud treats CI configuration as executable production-adjacent
code. Workflow actions are pinned to full commit SHAs so a moved release tag
cannot silently change code executed with repository credentials. A release
version comment remains beside every SHA for human review.

## GitHub Actions

| Action | Release | Immutable commit SHA |
| --- | --- | --- |
| `actions/checkout` | `v4.4.0` | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-node` | `v4.4.0` | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/upload-artifact` | `v4.6.2` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `pnpm/action-setup` | `v4.3.0` | `b906affcce14559ad1aafd4ab0e942779e9f58b1` |
| `astral-sh/setup-uv` | `v6.8.0` | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` |
| `aquasecurity/trivy-action` | `v0.36.0` | `ed142fd0673e97e23eac54620cfb913e5ce36c25` |
| `github/codeql-action` | `v4` | `793b778da9c9275a0f276522b27cb5fc14bba279` |

The SHAs were resolved from each canonical upstream Git tag. Annotated tags
were dereferenced to the underlying commit before pinning.

## Security binaries

`scripts/install-ci-security-tools.sh` downloads only versioned assets from the
canonical OpenGrep and Gitleaks GitHub repositories. It requires HTTPS, verifies
integrity before installation, and exits immediately on any mismatch.

| Tool | Version and asset | Integrity control |
| --- | --- | --- |
| OpenGrep | `1.29.0`, `opengrep_manylinux_x86` | SHA-256 `3365ef49d04893e01338d85d9bbd49b2bd5261ad4c9c0df0a6a0f8d44232ae13` |
| Gitleaks | `8.30.1`, `gitleaks_8.30.1_linux_x64.tar.gz` | Canonical checksum manifest, itself pinned to SHA-256 `061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae` |

GitHub does not mark either selected upstream release as immutable. OpenGrep
publishes certificate and signature assets but does not publish a standalone
checksum manifest. Bootstrapping a separate signature verifier would add
another executable acquisition path, so CI pins the canonical release asset's
published SHA-256 digest directly. Gitleaks publishes a checksum manifest; CI
pins that manifest's canonical digest and then validates the selected archive
against it. In both cases, replacement bytes at the versioned URL fail closed.

## Visual regression runtime

Linux screenshot and accessibility regression runs inside the official
Playwright 1.64.1 Noble image pinned to manifest digest
`sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f`.
The container receives only the two synthetic Keycloak test passwords and local
loopback URLs. Pinning the browser, operating-system libraries and fonts avoids
accepting visual drift caused solely by GitHub-hosted runner image updates. The
test runtime is not a production dependency or distributed application image.

## Version upgrades

Tool and action upgrades require separate approval. The maintainer must review
the canonical upstream release, resolve action tags to their underlying commits,
record the new human-readable versions and SHAs, refresh binary digests from
canonical release metadata, run focused integrity and security checks, and wait
for both repository workflows to pass on the new head.

Dependabot, Renovate, and equivalent automated dependency or action updates are
not authorized unless the Product Owner approves them separately. Hosted runner
labels remain managed by GitHub; their exact image versions are recorded in CI
logs because GitHub-hosted runner labels cannot be pinned to an image digest.

## Runtime malware scanner

The document-upload scanner uses the official Cisco Talos ClamAV Alpine image
`clamav/clamav:1.5.4`, pinned to manifest digest
`sha256:bda39705e291105049c3936e2803ac90b955172af8030f94f05dce1252df6c6d`.
The digest was inspected from Docker Hub on 2026-10-28 and scanned with Trivy;
that run reported no vulnerabilities. CI generates a CycloneDX SBOM and blocks
critical/high findings for this image. The selected manifest currently provides
`linux/amd64`; local Apple Silicon uses emulation, so an ARM deployment needs a
separately reviewed multi-architecture image.

ClamD is reachable only on the internal platform network. A separate network is
attached solely to ClamAV for FreshClam signature updates. No host port is
published. ClamD's TCP protocol has no authentication or encryption, so network
isolation is required; see the [ClamD protocol guide](https://docs.clamav.net/manual/Usage/ClamdProtocol.html)
and [official Docker guidance](https://docs.clamav.net/manual/Installing/Docker.html).

## Multi-architecture application images

The API runtime installs the hash-locked `requirements-runtime.txt` with the
installer already provided by the pinned, target-architecture Python image. The
installer and its metadata are removed before the final image is exported. This
avoids copying an `amd64` executable into an `arm64` runtime while preserving
`--require-hashes`, optional offline wheel installation and a non-root final user.

The local 2026-11-02 ARM build completed natively. Trivy reported zero High or
Critical vulnerabilities in the resulting API and web images. CI still rebuilds
and scans commit-bound images; support for an additional production architecture
must be demonstrated by a matrix build before that architecture is approved.
