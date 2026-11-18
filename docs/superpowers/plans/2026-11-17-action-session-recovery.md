# Action center session recovery

Goal: finish the preserved UI fix so expired sessions give a clear sign-in route, failed reloads hide prior tasks, and another company/user cannot reuse the previous action queue.

Architecture: existing React components, same-origin identity proxy and OIDC login; no backend, database, role or business-flow changes. Use the existing isolated worktree and a dedicated branch. User has requested autonomous continuation and decisions; implementation proceeds inline under that authorization.

Baseline: 1672dd2 / PR63. CP-ACTION-RECOVERY-00-20261118T021932Z preserves732 source files/Git including the pre-existing WIP, restored by hashes/modes/bundle and authenticated encryption. No database mutation planned.

Alternatives: a global authentication rewrite would touch every workspace; a targeted action queue fix completes the existing work with less regression risk. Select the targeted fix. Audit ready/start is separate: the current diagnostic and SQL disallow it, and changing plan version would invalidate the human assessments. Do not enable a cosmetic Start/Ready button.

## Task 1 — Complete and test the action queue reader

Files: `apps/web/src/lib/action-center-data.ts`, its `.test.ts`, existing `action-center-workspace.tsx`, `identity-shell.tsx`, `styles.css`.

- [x] Write failing tests for 401 versus403 versus network/server failure, invalid JSON/scope/shape and successful current data.
- [x] Add a typed reader returning data or a safe failure, using the current API and credential policy. Validate the display contract before rendering; do not expose response bodies as errors.
- [x] Integrate the reader with the preserved UI. Clear old tasks while loading, ignore out-of-order/unmounted results, retain explicit sign-in link, preserve company/user remount keys.
- [x] Run the full frontend unit suite, lint, typecheck and build. Preserve generated files and unrelated WIP without blanket staging.

## Task 2 — Verify user-visible recovery

Files: `apps/web/e2e/action-center.experience.spec.ts`; local fixture outside source; `CHECKPOINT.md`; `docs/reviews/ACTION_SESSION_RECOVERY_2026-11-17.md`.

- [x] Add browser regressions for populated→expired/denied/error, reauthentication link, context change and stale response. Use controlled fixtures, no credentials or business writes.
- [x] Exercise the actual UI through CUA against an isolated loopback fixture; save screenshots. Do not claim a mocked login as a real OIDC test.
- [x] Request a fresh whole-change reviewer, resolve material findings with regressions, run relevant checks and secret scan.
- [x] Create a final recovery checkpoint, commit only owned files and publish a draft PR against PR63. PR64: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/64 . No merge or production deployment; CI/browser execution pending.

Review focus: delayed previous-context responses; malformed200 bodies;401 must not look like lack of permissions;403 must not show previous tasks; changing companies must not preserve overview state. Browser automation runs in CI; local browser work uses CUA. Record any unavailable check as pending rather than PASS.

Ledger: targeted completion of preserved WIP selected; no global auth rewrite. Baseline118/final136unit PASS;18newreader tests; build/lint/typecheck PASS. Final review identified enum coercion and premature race assertion; corrected,3enumregressions RED→GREEN, full136suitePASS. CUA fixture validates presentation only, no new realOIDC or remoteDB isolation claim. Automated10browser cases remain pendingCI; standalone fixture servers closed. No deferred minor findings.
