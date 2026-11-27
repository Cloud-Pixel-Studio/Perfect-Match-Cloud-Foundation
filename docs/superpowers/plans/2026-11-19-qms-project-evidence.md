# QMS project-step supporting records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Cite and retire specific released document revisions and accepted source evidence within saved project steps, preserving history and current authority.
**Architecture:** Two typed link tables/routes, existing project/step optimistic versions, server-derived immutable snapshots and transactional typed audit. Scoped paginated candidate endpoints; focused client/component integrated into StepEditor.
**Tech Stack:** Existing FastAPI/SQLAlchemy/Alembic/PostgreSQL and Next/React/TypeScript; no new dependencies.
**Spec:** docs/superpowers/specs/2026-11-19-qms-project-evidence-design.md
**Interface:** docs/product/QMS_PROJECT_REFERENCE_API_CONTRACT.json

## Global Constraints
- Reads require projects.read and corresponding documents.read or control_instances.read at exact active unit; writes also projects.manage. No role/assignment bypass, new grants or source review/manage action.
- Citation never verifies a project step or ISO conformity; no status/note/assignment/date/source lifecycle changes; feature_pending unchanged.
- Link BEFORE trigger locks parent then step and advances both exactly once through0050 protocol. No new marker columns or weakened0050 guards. All SQL references public-qualified, search_path=pg_catalog,public,pg_temp.
- Match selected source/container versions; immutable source snapshots/rationale; soft removal with reason; no hard delete/restore/edit link endpoint.
- Existing project30-blank-set trim and Unicode code-point limits apply to new500-character rationale/removal reasons. Source labels copied unchanged; no unrelated normalization rewrite.
- GET snapshots scope/versions coherent with page; eligibility before pagination; limit1..50/default50, offset0..1000000, has_more sentinel; literal search max160.
- No demo/customer/production changes.0051 only disposable fixtures with recoverable encrypted before/after restore evidence. Dedicated branch, draft PR stacked on67; no merge/waiver/dependency updates. Preserve untracked apps/web/AGENTS.md.

## Review Focus
- Reference source read authority can disappear independently of project authority: initial absence is restricted, later401/403 clears through access invalidator; no stale source metadata.
- Parent/step/source versions may change during selection: rejected409 retains drafts; ambiguous5xx never auto-retries; explicit reload/adoption, already-committed outcomes inspectable.
- Sources can become superseded/obsolete/archived: snapshot remains, diagnostic state warns, no substitution or claimed current verification.
- Empty/off-end/filtered pages retain scope/versions and honest has_more; no source loss due legacy100/200 picker ceilings.
- New link mutations share parent/step locks with note edits/archive: one winner or conflict, complete rollback including audit and versions, unrelated content unchanged.

### Task 1: SQL/API foundation and integration evidence
**Owner files:** create apps/api/migrations/versions/0051_qms_project_references.py; apps/api/src/pmc_api/qms_project_references.py; apps/api/tests/test_qms_project_references.py; apps/api/tests/test_qms_project_reference_integrity.py; scripts/run-qms-project-reference-integrity.sh. Modify apps/api/src/pmc_api/models.py, main.py, audit_service.py and .github/workflows/quality.yml. Existing qms_projects helpers may be imported; do not change its payload/command semantics. No edits to0050.
**Interfaces:** Consume the JSON contract verbatim; produce the eight declared routes and typed receipts/pages. Audit actions qms_project.document_linked/document_unlinked/evidence_linked/evidence_unlinked, resources qms_project_document_link/qms_project_evidence_link; events include IDs/versions and rationale/reason hashes, not raw narratives/source labels.
- [ ] Write unit contract/auth/audit negative cases; run RED before implementation. Reject extra scope/snapshot fields, bool/zero versions, blank/BOM/oversized reasons, malformed kind and source/version pairing.
- [ ] Write real HTTP/directSQL integration cases, observe RED. Include project+source permissions, owner/coordinator/reader limitations, wrong company/unit/project/step/revision/evidence, suspended actors, duplicate active source, nonaccepted/unsafe/unreleased source and stale container/target versions.
- [ ] Implement additive0051 tables/FKs/RLS/snapshot/soft-removal/automatic version triggers and safe downgrade. Demonstrate source snapshots derive server-side and removal cannot alter them; actors/commands/versions cannot be forged. No source state locks or lifecycle modifications; implement the stated observation semantics.
- [ ] Implement API pages, literal search/candidates, coherent empty/off-end scope, exact201/200 compound receipts and audit atomicity. Refactor no working unrelated module.
- [ ] Verify add/remove advances parent+step once without changing status/notes/assignment/date; 409/audit failure restores every row/version. Exercise add-vs-note, add-vs-project archive and defined source-transition outcomes with bounded concurrency tests.
- [ ] Add independent ephemeral PostgreSQL harness with baseline0050→0051 empty up/down/up; encrypted61/63-table content restore/hash/tamper verification outside Git, separate keys, no owner/ACL/S3/IdP claim; nonempty reference/audit history blocks downgrade. Connect a new quality job.
- [ ] Run full new DB suite and existing93 project DB checks on new head, API unit/Ruff/format/mypy, ShellCheck/bash-n. Do not stage/commit others' files; write task report and return test/log paths and unresolved risks.

### Task 2: strict reference client and usable scoped UI
**Owner files:** create apps/web/src/lib/qms-project-references.ts/.test.ts, apps/web/src/components/qms-project-references.tsx, apps/web/e2e/qms-project-references.experience.spec.ts. Modify qms-project-planner.tsx, app/qms-projects.css, lib/identity-path.ts/.test.ts and lib/audit-view.ts/.test.ts only if labels are needed. Read current web AGENTS and bundled Next docs first. No backend writes.
**Interfaces:** Consume JSON contract and completed Task1. Props: context:ProjectContext, project:ProjectDetail, step:ProjectStep, canManage:boolean, disabled:boolean, onChange(ProjectDetail), onAccessLost(number), onEditingChange(boolean). Existing project helpers/trim/character bounds are reusable. Mutation receipt updates parent through existing callback; does not fabricate local authoritative rows.
- [ ] Write failing unit tests for same-scope pages/typed source snapshots, complete candidate pagination/has_more, empty/off-end pages, maxUnicode strings, source-capability loss, abort/late context, malformed metadata and exact receipts. Run RED.
- [ ] Implement readers and mutations: fresh actor/company/unit/source capability checks, no-store/include, CSRF, exact201/200, version/content receipt validation, private errors. GET stale-version state is distinct from context loss. Writes never retry automatically.
- [ ] Implement authorized source kinds, scoped search/page selection and rationale; visible snapshot/history/current-state warnings; exact revision download; explicit add/remove with captured versions and reasons. Explain accepted-in-source versus step verification and source attachment not re-evaluated. Handle no source capability as restricted rather than zero evidence.
- [ ] Preserve drafts across409/5xx/reloads; explicit refreshed-version adoption before retry. Already-added/removed outcome after an uncertain response is inspectable, not silently retried/discarded. Source search/page changes retain rationale but clear selection. Aggregate reference editing with step note editing and prevent competing local editors; metadata lock already exists.
- [ ] Add browser regressions for both kinds add/remove/history, read-only/missing source access, archived project, source changed/unavailable,409 and ambiguous response reconciliation, scope loss, pagination and375/1280px+Axe. Never create source approvals from this component.
- [ ] Run full web unit baseline282+new, lint/typecheck/build and enumerate browser cases. Document whether browser execution occurred; CI execution required before claiming PASS. No new library, source CRUD or business-data localStorage.

### Task 3: integration, recovery and draft publication (controller)
- [ ] Integrate Task1/2 reviewed results. Run compiled UI with explicit local synthetic fixture through CUA; verify add/remove/history, permissions, errors, responsive/light/dark without claiming liveOIDC/DB from fixture.
- [ ] Independent whole-branch review focused on the five Review Focus items; correct material regressions, preserve report and test evidence. No reviewer self-approval.
- [ ] Update CHECKPOINT and product/security report with implemented vs tested vs pending; source/Git checkpoint and explicitly selected encrypted evidence, secret scan, meaningful final checks. Preserve old work/AGENTS and original local commits.
- [ ] Publish dedicated branch/draft PR on67 with identical local/remote tree and expected-head lease. Run exact-head quality/CodeQL/security/browser CI; fix introduced failures, record vendor findings without waiver or deployment. No merge/prod.

### Authorized follow-on: synthetic demo rollout
User19November explicitly asks to upload all accumulated advances to the existing demo after completion. This supersedes the earlier no-demo restriction for the controller follow-on only; Task1/2 remain fixture/local-only. No production, merge, provider-image change, history downgrade or destructive data restoration is authorized.
- [ ] Read-only VM inventory; preserve older /opt/pmcloud and current demo configuration/provider identities.
- [ ] Build API/web from the reviewed exact source; retain current images and a precise additive override. Do not recreate bootstrap/IdP/storage/AV/PostgreSQL.
- [ ] Capture unique encrypted database/config backup outside Git, restore in a no-network temporary PostgreSQL, compare table inventory/content hashes from the same exported snapshot, verify tamper rejection, copy encrypted artifact/key separately off-VM.
- [ ] Apply0050/0051 only after the recovery verification and code/test/review gates. Verify schema and healthy API/web through ordinary TLS. No downgrade once new history exists.
- [ ] Using ordinary owner APIs, add only projects.read/manage for the dedicated synthetic pmc-demo-full in DEMO-PRACTICA. Preserve all existing permissions, passwords and examples.
- [ ] Add idempotent clearly synthetic saved project examples for the six journeys; connect eligible released revisions/accepted evidence to relevant steps. Unsupported journey steps remain pending, reported work unverified. Never overwrite user edits or approve sources automatically.
- [ ] Verify public marketing, real OIDC login/logout/account switch, saved projects and both reference kinds/history, exact PDF download hash, permission/tenant denials and previous module readbacks. Record actual execution, not all-buttons claims.
- [ ] Final encrypted recovery capture, visual proof, checkpoint and GitHub report; production security blockers remain visible.
