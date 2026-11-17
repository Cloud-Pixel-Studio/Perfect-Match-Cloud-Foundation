# Multiagent delivery plan — Perfect Match QMS SaaS

**Status:** implementation protocol, not a production readiness claim. This plan does not authorize autonomous merges, deployments, billing actions or secret access. Product Owner direction: complete functional QMS parity and validate security/operations before customers are onboarded.

## Current branch contract

At this checkpoint, `main` has PMC-04 workflows via PR #12; the large QMS foundation is on PR #13, and the branding/UI/audit-planning/Design Studio contributions are being reconciled into it via draft PR #19. A closed PR merged into a feature branch is not proof the functionality is present on `main`. Reinspect the live PR graph and CI before each implementation.

Existing modules **must not** be rebuilt: platform identity/tenant and organizational structure, workflow engine, document control, controls/evidence, risk, NCR, CAPA, action center, branding and UI surfaces. Internal audit planning (0040) is present in the feature-branch stack, while 0041 WIP is explicitly unvalidated and must not be executed.

## Workstreams and acceptance

| Order | Workstream | Primary/independent specialists | Required delivery evidence |
| --- | --- | --- | --- |
| P0 | Release-blocker vulnerability triage and supported upstream updates (#18) | application_security_reviewer, platform_sre / independent_reviewer | Exact current-head image digests, CVEs, fixes, scoped regression scans, no unchecked High/Critical gates |
| P0 | Finish safe PR-stack reconciliation (#19 -> #13 -> main) | qms_product_architect, qa_automation_engineer / independent_reviewer | No duplicated migrations, correct merged files, latest-head green checks, independent review |
| P0 | Production architecture and recovery baseline | platform_sre, database_rls_reviewer / application_security_reviewer | Separated dev/staging/prod, OIDC/TLS/MFA, secrets, verified backup/restore, RPO/RTO owner decisions, rollback drill |
| P1 | Internal audit end-to-end vertical beyond planning | qms_product_architect, backend_engineer, frontend_engineer / database_rls_reviewer, qa_automation_engineer | Scope, criteria, team, independence, evidence, findings, NCR handoff, Action Center and UI with forced-RLS negative tests |
| P1 | SaaS account and commercial entitlements | saas_commercial_architect, backend_engineer, frontend_engineer / application_security_reviewer | Secure onboarding, seats and invite lifecycle, ISO edition entitlements, idempotent subscriptions, suspension policy and billing evidence (commercial choices pending) |
| P1 | KPI/objectives and Management Review | qms_product_architect, backend_engineer, frontend_engineer / qa_automation_engineer | Historic measurements, scoped KPI trends, frozen Management Review snapshots, decisions and assigned follow-ups |
| P1 | Supplier and customer quality | qms_product_architect, backend_engineer, frontend_engineer / qa_automation_engineer | Evaluations, supplier scorecards, customer complaints, SCAR/8D, traceable NCR/CAPA links |
| P2 | People, competencies, training and calibration | qms_product_architect, backend_engineer, frontend_engineer / database_rls_reviewer | Role-scoped matrices, qualification status and expiry, equipment calibration and out-of-tolerance impact |
| P2 | Quality cost, migration, ISO profiles and integrations | qms_product_architect, saas_commercial_architect, backend_engineer / application_security_reviewer | Validated imports, mappings/edition history, proprietary standard metadata, authorized API, cost metrics |
| P2 | AI copilot (last, optional product extension) | qms_product_architect, application_security_reviewer / independent_reviewer | Per-tenant isolation, grounding, citations, human approval, PII boundary, cost/latency guardrails and adversarial evals |

## Definition of 100% / production gate

A module is **functionally complete** only after its complete acceptance matrix passes for users, permissions, tenant/unit boundaries, lifecycle, audit events, attachment security, error paths, accessibility, performance and real product-owner verification. A module title or a backend route is not proof of completeness.

A **production release candidate** additionally requires:
- The full intended commercial module inventory accounted for in a versioned acceptance matrix; no unsupported parity or ISO compliance statements.
- Green latest-head CI and independent review; reproducible container/runtime provenance and SBOM.
- Authenticated staging penetration testing, file upload malware/quarantine verification, object-storage negative tenant tests and production OIDC/MFA/TLS controls.
- Tested backup encryption and isolated restore, RPO/RTO acceptance, incident response runbooks, alerts, operational metrics and rollback rehearsal.
- Verified onboarding, billing and entitlement event idempotency, data lifecycle and support access.
- Product Owner approval to deploy; no customer data while blockers remain.

## Operating practice

Use the project-scoped Codex specialists described in `.codex/README.md`. Start with independent explorers/reviewers, then assign **one writer per overlapping code path**. Every new slice has an implementation contract, a dedicated branch, a reviewable PR, isolated tests, current SHA-specific evidence and a rollback story. The new agent files do not install a second runtime in the customer SaaS.

Source of truth: `AGENTS.md`, `CHECKPOINT.md`, `PRODUCT_SCOPE.md`, `docs/product/CONTINUE_FROM_HERE.md`, `docs/product/ODOO_FUNCTIONAL_PARITY_MATRIX.md` and current GitHub PRs, interpreted in that order with live code/tests taking precedence over dated summaries.
