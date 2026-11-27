# Project-step supporting records — design ·19 November2026

## Intent and authorization
Connect the persisted guide's individual steps to real existing records, so a company can explain what supports its reported work. User authorizes autonomous choices and reversible development/PR preparation. These are engineering decisions under that authorization, not newly approved ISO rules or commercial terms. No demo/customer migration, grants, merge or production deployment.

Baseline2425a32/PR67; workspace already isolated. CP-QMS-PROJECT-EVIDENCE-00-20261119T222615Z restored769sources/Git/hash/modes/tamper. Existing282web/109APIunit passed;666DBskip are not passes. Git remote agrees; no overlapping project-evidence PR found; main13e672a unchanged. Untracked apps/web/AGENTS.md preserved.

## Approaches
1. Notes/URLs alone: little code, but cannot prove source identity, scope or version. Rejected.
2. Typed document-revision and accepted-evidence references, reusing CAPA/NCR patterns: selected engineering approach. New project-step tables and routes are necessary; existing tables require different parents. Immutable snapshots and reasoned removal provide traceability while source authority remains separate.
3. Formal step acceptance/ISO readiness engine with frozen source assessments: deferred. It requires normative applicability, competent independent decisions and a broader state machine. References do not implement it.

## Boundaries
- Two kinds only: released clean document revisions; accepted control-implementation evidence on an active implementation. Both must belong to the project's exact company/unit; any process within that unit may support the step.
- No new capabilities. Project read plus documents.read or control_instances.read for each respective kind; writes also require projects.manage. No owner/admin bypass or automatic grants. Source review/manage is unnecessary for citing already authorized records.
- Project, step and source IDs derive from authenticated scope; request bodies forbid tenant/unit/snapshot fields. Existing actor, active-unit, company suspension and CSRF controls apply.
- Feature-pending steps may carry planning references, but their status remains feature_pending. Links never change notes/status/assignments, source lifecycle or acceptance, grants, ISO status or readiness.
- Add/remove require current project and step versions; remove also requires current link version and a reason. Add requires a rationale and selected source/container versions. No hard deletion or restoration of a removed link; re-adding makes a new historical row.

## SQL and consistency
Add0051 after0050, two forced-RLS tables with composite step/company/unit FKs and the appropriate source FKs. Add a suitable unique step scope key. Active duplicates are unique per step and cited revision/evidence. No DELETE/TRUNCATE runtime privilege. Snapshots, identifiers, rationale and creation metadata are immutable; only active→removed, removal metadata and last command versions can change.

The link's BEFORE trigger locks project then step, validates exact source privileges, open project/catalog and expected next versions. It derives source snapshots and actual actor/time. It advances project and step exactly once itself using the existing0050 protocol: parent step_write_id, child source_project_version, updated actor/timestamps. It must not weaken/replace0050 or introduce marker columns into existing project/step tables. API supplies expected+1 receipt columns, flushes the link, refreshes parent/step, records the typed link event and commits together. A duplicate, stale source/version, scope failure or audit failure rolls back all three rows. Direct SQL cannot insert/update a reference without this trigger-mediated version movement. Unsupported command GUC values fail closed.

All new function relation/helper references are public-qualified, search_path=pg_catalog,public,pg_temp. Do not repeat the prior namespace defect. New text fields reuse the project30-character trim set and500-code-point reason/rationale limit. Source labels are copied unchanged, bounded by their source contracts; do not normalize unrelated document/control data.

Source lifecycle is observed using PostgreSQL statement snapshots, as in the existing typed links; this slice is not a formal source-freezing gate. Add validates active/clean/released or accepted/active source and exact selected container/target versions at validation. A source transition before that check causes conflict; a later transition can leave a historical reference. Current source state is a diagnostic read, with observed_at, never proof of step applicability. No new lifecycle locks/triggers on documents or control implementations. Source metadata FKs preserve identity; future source supersession/obsolescence/archive does not replace or erase the reference.

Document snapshots: process, code/title, revision, fileSHA256, document and revision versions. Evidence snapshots: process, implementation ID/code, evidence name, implementation/evidence versions. Accepted source evidence is immutable; its attached document is not re-evaluated by a project reference. State that limit in UI. Current-state values are defined by the API contract.

## API
Authoritative interface: docs/product/QMS_PROJECT_REFERENCE_API_CONTRACT.json. New router shares /qms-projects prefix. No changes to existing project payloads or commands.
- GET/POST /{project}/steps/{step}/document-links and evidence-links; POST .../{link}/remove.
- GET .../document-candidates and evidence-candidates: project/unit-scoped, properly paginated eligible sources. This avoids the legacy100-revision and200-evidence picker ceilings. Search is literal, not wildcard expansion.
- List/candidate pages retain project/step scope and versions even when offset is past the last row. Version metadata and listed rows come from one SQL statement snapshot. Link pages include active and removed history, active first, then created_at/id descending. Candidate ordering is source code/id. limit1..50/default50, offset0..1000000, has_more from limit+1 before slicing.
- Mutation receipt is {project:ProjectDetail,link:TypedLink}. Project/step versions advance once, unrelated plan fields remain unchanged. Event actions/resources are explicit for both kinds, transactional and hash rationale/removal text rather than copy narratives into audit. Downgrade refuses link or corresponding audit history; empty up/down/up remains possible.

## UX/client
New focused supporting-records component within StepEditor, after saved follow-up, before unit-wide observations. Separate Document and Accepted evidence choices; show only authorized source kinds. Read-only users see authorized references/history. Missing source read authority is explained, not shown as zero evidence. Active/removed cards show cited snapshot, versions, rationale and observed current-state warning. Exact cited revision download uses the existing secured file endpoint. No Accept/Approve/Complete-step command.

New client module validates before/after identity, active scope and exact capabilities; no-store/include and CSRF for writes. Validate every page/receipt's scope, IDs, limits, kinds and versions. Candidate/GET versions that differ from the mounted project produce a stale-data state and request explicit parent reload, not silent version adoption.401/403/context mismatch clear through existing access invalidator.409 keeps the selection/reason; reload current project and explicitly adopt versions before retry.5xx/malformed/ambiguous receipts are unconfirmed, with no automatic retry. Notes/rationale never go to localStorage.

Aggregate reference drafts with existing step drafts in onEditingChange; global module/company/unit/step navigation remains blocked. Do not let source add/remove and note editors overwrite each other's draft flags. Metadata editor already disables step management. Incoming project updates do not discard a reference draft. Archived project shows authorized history but disables add/remove and source-picking actions. Source status changes/removed links do not manufacture completion percentages.

Use current project tokens/classes,44px controls, focus/keyboard semantics, responsive single column and reduced motion. Search/page switches in source picker keep entered rationale and clear stale candidate selections. Empty/loading/error/forbidden/partial lists are explicit.

## Validation / exclusions
Prove HTTP and direct-SQL company/unit/step/source pairing, exact capabilities, no role/assignment bypass, suspension/revocation, stale parent/step/link/source versions, active duplicate prevention, source snapshot derivation/immutability, guarded removal, archived history, audit rollback, add-vs-note/archive races and stated source-lifecycle behavior. Source-state eligibility is checked before candidate pagination. Test literal percent/underscore search, empty/off-end pages, accepted vs draft evidence, retired/superseded targets, fake source metadata, actor/command/version tampering, whitespace/BOM/Unicode boundaries and downgrade protection. References never alter source or follow-up meaning.

Frontend tests cover strict cross-context parsing, source-capability loss, malformed/late pages, rejected409 vs ambiguous5xx, preserved drafts/rebase, compound receipt versions, no-write read-only/archive, real reference add/remove history and375/1280px browser/axe. Baseline tests remain operational. Use disposable PostgreSQL and encrypted before/after content restoration; no customer data. CodeQL/security/visual CI and independent review precede any integration. Existing vendor security gate remains binding; no waivers/deployments.
