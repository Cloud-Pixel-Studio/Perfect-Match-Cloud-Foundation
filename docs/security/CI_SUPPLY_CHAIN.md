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
