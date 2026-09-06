# Dependency and License Policy

Material dependencies require a purpose, pinned version, canonical source,
license, and necessity assessment. MIT, Apache-2.0, BSD, and ISC are preferred.
GPL requires review. AGPL, SSPL, commercial-only, and unknown licensing are
blocked unless the Product Owner and legal review explicitly authorize them.

Perfect Match Cloud source remains proprietary; third-party licenses apply only
to their respective components. Dependencies are kept narrow and mature.

SeaweedFS Community Edition is approved for local S3-compatible object storage:

- Source: https://github.com/seaweedfs/seaweedfs
- Version: 4.45
- Image: `chrislusf/seaweedfs:4.45`
- License: Apache-2.0
- Purpose: local-only S3-compatible storage behind a provider-neutral interface
- Necessity: proves storage portability without AWS resources or customer data

The pulled image digest is recorded in checkpoint evidence. MinIO is prohibited.

pnpm permits install scripts only for the explicitly listed `unrs-resolver`
package, an MIT-licensed native resolver required transitively by the approved
ESLint toolchain. Other dependency build scripts remain denied by default.

The backend uses BSD-licensed `pg8000` for PostgreSQL connectivity. Optional
Sharp/libvips Linux image binaries are excluded because the small local brand
asset is served unoptimized and does not require that LGPL runtime surface.
