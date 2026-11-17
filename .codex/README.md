# Perfect Match Cloud — Codex specialist agents

Project-scoped Codex agents live in `.codex/agents/*.toml`. Codex clients that support custom subagents can discover them when this branch is checked out. These files configure roles; committing them does **not** start a remote coding worker.

## Why native Codex agents
The existing repository already has `AGENTS.md`, `.ai/agents/team.yaml`, an issue-to-PR intake policy and quality/security workflows. Native Codex specialists reuse this context and do not add dependencies, API keys, network privileges or autonomous execution to customer-facing PM QMS.

The built-in `explorer` agent should first map code and active PRs. Then use the specialist agents only for bounded and genuinely independent tasks:

| Agent | Task | Edit scope |
| --- | --- | --- |
| qms_product_architect | QMS requirements, evidence, parity and acceptance | Read only |
| saas_commercial_architect | Tenants, seats, ISO entitlements, billing contracts | Read only |
| backend_engineer | FastAPI domain implementation | Assigned API files only |
| frontend_engineer | Next.js QMS UI implementation | Assigned web files only |
| database_rls_reviewer | PostgreSQL RLS, migrations, data boundaries | Read only |
| application_security_reviewer | OIDC, secrets, CVEs and release gates | Read only |
| qa_automation_engineer | Isolated deterministic regression tests | Assigned test files only |
| platform_sre | Staging, backup/recovery, monitoring and release | Plan first; bounded infra changes |
| independent_reviewer | Separate post-implementation review | Read only |

Design Studio already has five creative role contracts in `.ai/agents/design-studio.yaml`. Reuse those contracts instead of introducing a second design asset agent stack.

## Operating sequence

1. Read `AGENTS.md`, `CHECKPOINT.md`, `PRODUCT_SCOPE.md`, `docs/product/CONTINUE_FROM_HERE.md` and the latest PRs. Check current `main` and stacked PR branches, not only a stale feature matrix.
2. Use `explorer`, `qms_product_architect`, `saas_commercial_architect`, `database_rls_reviewer`, and `application_security_reviewer` in parallel **only for independent read-only investigation**, with concise evidence outputs.
3. Select one bounded implementation slice, with one implementing writer per overlapping file. Record the existing functionality, acceptance criteria, affected files, security invariant, test command, data migration and rollback impact.
4. Have `backend_engineer` or `frontend_engineer` implement that scope; `qa_automation_engineer` owns separate test files by agreement. Cross-module changes must be sequenced, not concurrent edits to the same file.
5. Have `database_rls_reviewer`, `application_security_reviewer` and `independent_reviewer` review the diff after implementation, using current commit-specific test evidence.
6. Open a draft PR. Run all required quality, CI security, disposable DB, browser/axe, SBOM and recovery checks. A failure blocks release; don't suppress or bypass it.
7. Merge/deploy only through human-reviewed protected branch procedures and an authorized release gate. Do not claim production readiness or ISO certification merely because CI passed.

**Example request in a Codex workspace**

> Analyze the latest development stack without duplicating PRs. Ask explorer and qms_product_architect to map existing work, database_rls_reviewer and application_security_reviewer to independently identify risks, and saas_commercial_architect to define tenant lifecycle gaps. Return a prioritized contract with exact paths and tests. Delegate the first safe bounded implementation to backend_engineer, write focused tests with qa_automation_engineer, and obtain independent_reviewer feedback. Do not merge, deploy or disable security gates.

## Safety and execution limits

Custom-agent instructions are behavioral contracts, **not** security sandboxes. A read-only instruction does not replace permissions or containment. Run Codex with the appropriate parent sandbox and approval policy, separate credentials by environment, and never grant agent workers production secrets. `max_concurrent_threads_per_session = 4` limits parallelism to reduce conflicting edits. No worker is started simply by pushing these files.
