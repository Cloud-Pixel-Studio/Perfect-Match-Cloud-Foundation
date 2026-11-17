# Integration and demo verification —17 November2026 UTC

The user explicitly requested completion/merge of all open PRs and demo testing.
36 open PRs were inventoried by exact head SHA, base and current CI. Every head
passed quality and CodeQL; every head's Foundation security workflow failed.
The JSON companion records all36 individually. No original PR was merged or
closed merely to reduce the counter; no branches or worktrees were deleted.

## What is integrated

All36 head commits are ancestors of the local `codex/merge-demo-integration`
candidate. Dedicated merge commits reconcile the lateral branches; existing main
and PR branch refs remain unchanged. This is **candidate integration**, not a
claim of36 GitHub merges or promotion to main. The user's authorization removes
the previous need to ask again for ordinary validated merges; it does not authorize
bypassing failed checks or production deployment.

Main's active ruleset22409098, Protect main foundation gates, requires backend,
frontend, shell, **security**, tenant/audit/organization/workflow integrity,
up-to-date checks and review-thread resolution. Its bypass actor list is empty.
The rule was read from GitHub, not inferred from the legacy protection response.
No rule, scanner severity or gate was relaxed.

Reconciliation decisions:

- Agent20/22 configurations and lease/reconcile utilities retained;11 manifests
  validate. No external agents, services or automated development were started.
  Their standalone document_control prototype remains a pure domain component,
  not a second HTTP document engine or an activated replacement.
- Architecture/flow/operability42/43/45 reports, fixtures and evidence retained.
  Incoming CHECKPOINT files are archived as CHECKPOINT_PR42/43/45; latest state
  remains in the brief root checkpoint.
-46's permission pagination announcements retained and exercised in the browser.
-49's BEMS assets/guide/goldens retained as an optional candidate variant. Official
  Perfect Match QMS remains the default identity. Responsive touch targets,
  reduced motion and tour ARIA improvements retained. Active Perfect Match
  screenshot baselines were not replaced by BEMS goldens.
-51/52 KPI calculations and proposed metric catalog retained and tested; no false
  live KPI panel was activated. Empty denominators/missing observations remain
  distinct from a real0 result.
-50/53 privacy/evidence hardening ancestry reconciled without losing59's fixes.
- Two old pin-negative tests now mutate the actual current pin, assert the input
  changed, and still demand rejection; they no longer silently replace a missing
  hardcoded4.51 string. No assertion was weakened.
-45's strict expected-failure marker for minimal document reviewers was removed:
  with47 present, approve/reject must now pass without author/release/obsolete
  grants. The five HTTP operability cases are included in the suspension harness.
- The demo exercise no longer falsely reports0048 from a constant. Its API-only
  harness does not inspect schema; real deployment inventory independently
  confirms0049. The earlier successful report's stale label is not schema proof.

## Validation on the candidate

| Scope | Result |
| --- | --- |
| API unit run |99 PASS;573 DB tests skipped outside their harnesses, not counted as passed |
| HTTP/PostgreSQL suspension, modules, documents, action center, Workflow |104 PASS |
| Internal audits: planning through competence/read-consistency |127 PASS; populated-history destructive downgrade guard PASS |
| Permission-history HTTP/RLS/cursor boundaries |42 PASS |
| Frontend unit tests |118 PASS /19 files |
| Root integration/tooling regressions |79 PASS;2 obsolete pin tests first failed, then corrected |
| API Ruff/format/mypy |82 files PASS |
| Frontend lint/typecheck/build; ShellCheck;11 agent manifests |PASS |
| OpenGrep |6 rules/117 Python files/0 findings; pre-existing PEP695 partial parsing in control_definitions.py, not full coverage |
| Gitleaks |Working tree0;282 candidate-ancestry commits0 |

The273 DB cases above are distinct. The first private history harness used a
wrong disposable DB name and was rejected by its safety assertion; the owned
fixture name was corrected, without changing that assertion or using real data.
All DB test containers were independent, loopback-only and tmpfs-backed.
No new complete browser/visual CI result is claimed until this exact combined
candidate runs. Prior PR59/fa4032 independently passed158 browser cases including
its two download/readonly/print-layout/axe scenarios; that is parent evidence.

## Updated real local demo

After verified recovery, only API/web were recreated from the complete candidate
source. API dependencies were unchanged; local web uses Next16.4.5. The actual DB
was migrated0048→0049, so company suspension protection and the full permission
history are now active in the demo. Rootfs read-only, cap_drop ALL,
no-new-privileges and health remained enabled. Odoo and the original/Studio WIP
were not touched.

Vendor containers were **not** upgraded or recreated. Candidate Compose pins do
not describe their current binaries. Keycloak/SeaweedFS/PostgreSQL/ClamAV local
state and volumes were retained; no production was touched.

Real OIDC/API/proxy checks:

- Demo inventory readback PASS, preserving existing examples and edits.
-47 exercise checks PASS: processes, controlled PDFs, risks, NCR/CAPA, controls/
  evidence, audit/program/scope planning, workflows, history and foreign-company
  denial. Creates only new synthetic QA; one temporary test grant is revoked,
  no deletes. This is not zero-write or universal UI acceptance.
-8 Workflow executor publication/start/transition/retirement checks PASS.
-24 read-only preparation/competence API/proxy checks PASS, including foreign
  company denial and no-store.
-8 read-only permission-history checks PASS;39 scoped grant-history rows gathered
  without duplication. Owner/member minimization, cursor/viewer/filter binding,
  wrong-person denial and proxy parity verified. No grants changed by this test.

Total87 real checks. Browser additionally showed member-only history→Page2 with
20 rows and the new live announcement, downloaded LAB-AUD-002/v5 from the integrated
API/web, and loaded marketing with the official identity. Captures are in ignored
`artifacts/previews/2026-11-17-merge/`. No real approvals, certification, complete
Odoo parity, audit execution/reporting or commercial onboarding is asserted.

## Security blocker and remediation

PR59 artifact14295540191/run44005465963 was downloaded, ZIP-digest verified and
bound to fa4032e. It reports7 HIGH: Keycloak26.8.2 has6, SeaweedFS4.53 has1; API,
web, PostgreSQL and ClamAV0 High/Critical. Runtime,158 browser checks and passive
ZAP completed; only the final release gate failed.

A newer official [SeaweedFS4.54](https://github.com/seaweedfs/seaweedfs/releases/tag/4.54)
was verified against Docker Hub metadata and its immutable go.mod. x/net is0.62.0.
The exact OCI index is pinned in candidate Compose and security scanning, and the
candidate evaluator uses4.54. A fresh native Trivy remote Linux/AMD64 scan found
**0 High/Critical**. It did not consume or modify real storage volumes. The full
combined CI must still validate runtime/S3 and scanner binding for this pin.

Latest official Keycloak release remains26.8.2. Its verified candidate findings:
CVE-2026-91403 in OpenJDK (will_not_fix), CVE-2026-119373/119374/119379/119586 in
sqlite-libs (no fixed RPM recorded), CVE-2026-102554 in Guava33.6.0-jre
(fix33.7.2). This does not establish exploitability in every app, but it also does
not justify a non-affected waiver. No unsupported JAR/JDK replacement, SQLite
removal, scanner exclusion or invented zero was used.

Thus the candidate still has **six known Keycloak HIGH findings blocking the
required main security check**. Original PRs are preserved while the combined
candidate gets exact CI and independent review. Main merges remain unperformed.
PM production decision remains NO GO; business completeness is also pending.

## Recovery

- CP-MERGE-DEMO-00-20261117T031156Z:564 source/Git entries restored/hash-verified.
- CP-MERGE-DEMO-02-20261117T032553Z:697 entries after branch reconciliation,
  encrypted restoration and Git bundle verification PASS.
- DB pre-migration CP-MERGE-DEMO-DB-00-20261117T033000Z:0048/57 tables restored in
  an isolated no-network instance, including ACL/roles/sequences and row/schema
  inventories. The ID is a reference; private manifest captures actual UTC times.
  Actual previous API sources were encrypted/decrypted byte-identically as well.
- DB post-migration CP-MERGE-DEMO-DB-06-20261117T034050Z:0049/57 tables, isolated
  restore PASS. Backup/keys remain outside Git; no new S3/Keycloak restore claim.
- Previous application/migration images retained as
  pmcloud-api/web/migrate:before-merge-demo-20261117. Application rollback is
  separate from schema rollback; do not downgrade or restore the real DB casually.

Final delivered source/Git and detailed logs/screenshots are sealed separately
before handoff. Any publication must preserve the merge-parent graph and verify
that the remote tree equals the tested local tree. No force-push, worktree reset,
branch deletion, history erasure or automatic production deployment is authorized.
