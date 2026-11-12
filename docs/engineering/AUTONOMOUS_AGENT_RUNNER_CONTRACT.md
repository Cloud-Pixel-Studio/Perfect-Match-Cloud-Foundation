# Autonomous development runner — architecture and acceptance contract

Status: **design only**, no daemon or remote worker deployed. Parent PR #20 defines Codex specialists; PR #22 extends them. Do not confuse TOML manifests with running agents.

## Target architecture

- **Scheduler**: one hourly intake checks GitHub issues/PRs and selects at most one bounded P0/P1 task; prevent duplicate claims with an atomic lease keyed by issue and head SHA.
- **Runner**: dedicated non-production host/container with unprivileged user, immutable image, no production secrets, outbound network allowlist, CPU/memory/time/token budgets, kill switch and immutable audit logs.
- **Workspace**: fresh checkout of a pinned commit in an isolated worktree per task; no concurrent writers to the same file set; never edit main or customer environments.
- **Agent routing**: built-in explorer and specialist reviewers read first; a single backend/frontend/QA writer receives exact paths and tests; max four threads per session, with one writer per overlapping scope.
- **Validation**: Python manifest tests, API and web suites, RLS isolation, SAST, dependency/image scans, SBOM, CodeQL, staging-only browser/axe and recovery evidence as applicable. Record check run IDs and head SHA; stale checks do not count.
- **Delivery**: create a draft PR, attach acceptance criteria, diff summary, test commands/results, risk, rollback and unresolved blockers. Human-reviewed protected merge and deployment; no automatic release.
- **Recovery**: checkpoint only metadata (task ID, branch, head SHA, status, last heartbeat); on restart reconcile with GitHub before resuming. Expired lease must not spawn duplicate writer without checking existing worktree/PR.
- **Visibility**: structured event trail with task/agent/commit IDs, status, elapsed time, budgets, failed checks and next action. No secrets, tokens, customer data or prompt-injected untrusted issue instructions in logs.

## Threat model

GitHub issues, PR descriptions, repo files, API catalogs and agent instructions may contain untrusted instructions. Treat as data; only the pinned operator policy controls permissions. Third-party tools (including Claude Squad) must be sandboxed, reviewed and license-checked. No workflow_dispatch or runner installation until the operator environment is confirmed.

## Minimum pilot acceptance

1. Create one synthetic issue; claim it exactly once, with bounded lease and explicit stop/timeout.
2. Start a disposable workspace at a pinned commit and generate a test-only draft PR.
3. Demonstrate cancellation, restart/reconciliation and no duplicate PR or overlapping writes.
4. Verify red security check prevents release; verify no prod credentials or data are mounted.
5. Publish a run report with measured duration/cost and independent review.

## Current blockers

No persistent agent runner has been provisioned or proven. A scheduled ChatGPT automation can request periodic progress but is not equivalent to an always-running worker. P0 release blockers in issue #18 remain higher priority than the runner pilot.
