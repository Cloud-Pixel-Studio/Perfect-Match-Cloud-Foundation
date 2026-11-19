# Persistent QMS project planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Save and resume a scoped QMS project and step planning without claiming verified normative progress.
**Architecture:** Existing guide plus new RLS-backed project/step records. Versioned server catalog, explicit unit capabilities, transactional audit and optimistic versioning. No deployed DB mutations.
**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/Alembic; Next/React/TypeScript, existing tokens/proxy.
**Spec:** docs/superpowers/specs/2026-11-18-persistent-qms-projects-design.md

## Global Constraints
- projects.read required for reads; projects.read AND projects.manage required for writes at exact unit, no autogrants.
- catalog_version guided-qms-v1; statuses not_started/in_progress/blocked/reported, product gaps feature_pending immutable.
- reported is unverified work, no completed/ISO-ready percentages.
- Preserve unrelated apps/web/AGENTS.md and all local work; no demo/production migration/deployment.
- No new dependencies, no scanner exclusions or vulnerability waivers.

## Review Focus
- Other-company/unit IDs, inactive actor/unit/member and revoked capabilities must fail closed at API and direct SQL.
- Simultaneous project/step writes serialize on parent and reject stale expected versions without partial audit.
- Product gap and catalog edits cannot manufacture completion; archived plans immutable until explicit restoration.
- Context switch, 401/403 and late/malformed responses clear prior project state and mutation receipts.
- Scope observations remain distinct from project-linked evidence, and reported notes cannot look verified.

### Task 1: backend and database foundation
Files: new apps/api/src/pmc_api/qms_projects.py, qms_project_catalog.json, migration0050_qms_projects.py, tests/test_qms_projects.py and test_qms_project_integrity.py, scripts/run-qms-project-integrity.sh. Modify models.py, main.py, qms_access.py, audit_service.py. Worker owns these files only.
Interfaces: root writes docs/product/QMS_PROJECT_API_CONTRACT.json and authoritative catalog snapshot before dispatch. API /qms-projects list/create/detail/patch/status, /{id}/steps/{step_id} patch. See contract for exact types/versions. Reuse actor_context, require_capability, CSRF and typed audit writer.
- [x] Write unit/integration negative tests first; observe RED. Include atomic rollback on audit error, raw SQL identity/version/scope, cross-company/unit reads, archived scope, no automatic grants, blocked/reported note gates.
- [x] Implement additive migration/API/model/audit. Frozen catalog creates all selected steps once. No deletion. Downgrade refuses nonempty project/grant/audit history.
- [x] Run disposable PostgreSQL up/down/up and HTTP/directSQL tests with dedicated ephemeral port/tmpfs. Take encrypted dump+restore/hash verification before/after migration in this disposable fixture; no customer DB.
- [x] Run API Ruff/format/mypy/unit and meaningful existing boundary regressions. Do not stage/commit others' files.

### Task 2: scoped browser client and guide integration (root)
Files: new apps/web/src/lib/qms-projects.ts/.test.ts, components/qms-project-planner.tsx, app/qms-projects.css; modify guided-journey-workspace.tsx, qms-access-workspace.tsx, layout.tsx, guided-journeys.test.ts, browser fixture tests.
Interfaces: QMS_PROJECT_API_CONTRACT.json, JSON catalog matches guide44steps. Planner props tenantId,userId,unitId,journeyId,currentStepKey,onSelectProjectJourney; caller remounts by actor/company/unit.
- [x] TDD strict response/scope/identity/capability reader and CSRF mutation, stale/abort/401/403/409 contracts; verify RED→GREEN.
- [x] Implement project list, create/edit/archive/restore and step planning. Freeze journey on project selection; explicit return to generic guide. UI labels reported as pending verification, product gaps disabled; no automatic status from unit counts.
- [x] Manual CUA on compiled local build, desktop/mobile/light/dark/errors/scope changes; no alternate local browser driver. Enumerate automated browser cases; CI pending unless executed.
- [x] Run web208baseline+new tests, lint/typecheck/build and frozen catalog equality check.

### Task 3: independent review, recovery and publication (root)
- [x] Independent read-only review of complete diff, focused RLS/history/access/concurrency/cross-context tests; correct material findings and verify scoped follow-up.
- [x] Update CHECKPOINT/product report, encrypted source/Git checkpoint, staged secret scan/diffcheck; publish dedicated branch/draft PR based on guided journeys. Local/remote tree equality and no force push.
- [x] Record actual tests, migration/restoration evidence, pending browser/security gates, no deployment. Preserve existing demo runtime.

Ruling: user opted for autonomous delivery across session; no new approval cycle for reversible local implementation. Formal completion remains excluded until an explicit evidence/review engine exists.
