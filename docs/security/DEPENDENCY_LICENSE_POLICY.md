# Dependency and License Policy

Material dependencies require a purpose, pinned version, canonical source,
license, and necessity assessment. MIT, Apache-2.0, BSD, and ISC are preferred.
GPL requires review. AGPL, SSPL, commercial-only, and unknown licensing are
blocked unless the Product Owner and legal review explicitly authorize them.

Perfect Match Cloud source remains proprietary; third-party licenses apply only
to their respective components. Dependencies are kept narrow and mature.

## Material dependency register

| Component | Selected version | Canonical source | License | Purpose and necessity |
| --- | --- | --- | --- | --- |
| Python | 3.12 | https://www.python.org/ | PSF-2.0 | Supported backend runtime. |
| uv | 0.12.10 | https://github.com/astral-sh/uv | MIT OR Apache-2.0 | Reproducible Python environment and lock management. |
| FastAPI | 0.141.1 | https://github.com/fastapi/fastapi | MIT | Typed HTTP API foundation. |
| SQLAlchemy | 2.0.52 | https://github.com/sqlalchemy/sqlalchemy | MIT | Provider-independent relational data access. |
| Alembic | 1.19.2 | https://github.com/sqlalchemy/alembic | MIT | Database migration foundation. |
| Pydantic | 2.13.5 | https://github.com/pydantic/pydantic | MIT | Typed validation and API contracts. |
| boto3 | 1.43.89 | https://github.com/boto/boto3 | Apache-2.0 | Standard S3-compatible client surface. |
| pg8000 | 1.31.5 | https://github.com/tlocke/pg8000 | BSD-3-Clause | PostgreSQL driver without a copyleft runtime dependency. |
| Uvicorn | 0.52.4 | https://github.com/encode/uvicorn | BSD-3-Clause | ASGI application server. |
| Node.js | 24.20.0 LTS | https://nodejs.org/ | MIT | Supported frontend and build runtime. |
| pnpm | 12.3.4 | https://github.com/pnpm/pnpm | MIT | Pinned workspace package manager with install-script policy. |
| Next.js | 16.3.4 | https://github.com/vercel/next.js | MIT | Web application and server-rendering framework. |
| React | 19.2.8 | https://github.com/facebook/react | MIT | Component rendering foundation. |
| TypeScript | 6.0.3 | https://github.com/microsoft/TypeScript | Apache-2.0 | Strict static typing for the web application. |
| Lucide React | 1.41.0 | https://github.com/lucide-icons/lucide | ISC | Accessible interface icon set. |
| PostgreSQL | 18.6 | https://www.postgresql.org/ | PostgreSQL | Local relational data service and future RDS-compatible engine. |
| SeaweedFS Community Edition | 4.45 | https://github.com/seaweedfs/seaweedfs | Apache-2.0 | Local S3-compatible object storage. |

The standalone engineering tools are Docker Engine 29.8.0 (Apache-2.0 core),
Docker Compose 5.5.1 (Apache-2.0), OpenGrep 1.29.0 (LGPL-2.1), Trivy 0.74.0
(Apache-2.0), Gitleaks 8.30.1 (MIT), pip-audit 2.10.1 (Apache-2.0), OWASP ZAP
stable image digest `sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef`
(Apache-2.0), Ruff (MIT), mypy (MIT), pytest (MIT), ESLint (MIT), Vitest
(MIT), and ShellCheck (GPL-3.0). These tools are required standalone build or
audit utilities; their code is not linked into or distributed as the
proprietary application.

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
