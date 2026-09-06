# Perfect Match Cloud

Perfect Match Cloud is a proprietary, greenfield, SaaS-first quality management
and compliance platform owned by Perfect Match Investments, LLC. It is being
built as an independent multi-tenant product and is not an Odoo or ERP project.

PMC-00 establishes the local engineering, security, governance, and executable
application foundation. It does not implement QMS business modules or claim
regulatory certification.

## Roadmap namespace

- PMC-00 Foundation
- PMC-01 Identity & Multi-Tenancy
- PMC-02 Audit Engine
- PMC-03 Organization Structure
- PMC-04 Workflow Engine
- PMC-05 Document Control
- PMC-06 NCR
- PMC-07 CAPA
- PMC-08 Risk
- PMC-09 Internal Audits
- PMC-10 Supplier Quality
- PMC-11 Objectives & KPI
- PMC-12 Management Review
- PMC-13 Compliance Engine
- PMC-14 Perfect Match AI

## Local development

Requirements are Docker Engine with Compose, Python 3.12, uv, Node 24, and pnpm.
Local credentials live outside the repository in
`~/.config/pmcloud/dev.env`; `make configure` creates them with restrictive
permissions.

```bash
make configure
make up
make health
make logs
make down
```

The web shell listens on `http://127.0.0.1:3000`, the API on
`http://127.0.0.1:8000`, and the development S3-compatible endpoint on
`http://127.0.0.1:8333`. PostgreSQL has no host port.

## Validation

```bash
make lint
make typecheck
make test
make build
make security-focused
make checkpoint
```

`make security-focused` runs local checks only. The final checkpoint additionally
uses Trivy, Gitleaks, dependency audits, application image scans, a CycloneDX
SBOM, and a passive OWASP ZAP baseline against the disposable local application.

The current UI and API are a development foundation only. No QMS business
modules, production identity, tenant provisioning, AWS infrastructure, or
certification claims are implemented.

## Proprietary status

No open-source license is granted for Perfect Match Cloud itself. See `LICENSE`.
