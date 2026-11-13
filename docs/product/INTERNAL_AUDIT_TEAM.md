# Audit planning team ·13November2026 UTC

## Implemented boundary

An audit now has versioned planning assignments for active company members.
Roles are auditor and audited participant (auditee); responsibilities are authored
notes. The existing parent lead-auditor field remains authoritative for leadership.
An active audited participant cannot be selected as lead, and the current lead
cannot be changed into an audited participant. SQL enforces both write directions.

Assignment **does not grant access, execution capability, qualifications or
independence approval**. It is planning data, consistent with the existing lead
assignment. A person may be planned before execution access is granted; the
future readiness/execution commands must check current authority, team membership
and independence. None of those execution commands is exposed by this slice.
Lead assignment and team retirement remain separate commands; retiring a roster
record does not silently edit the lead field. Future readiness must reconcile them.

Only internal active company users can be assigned; contacts/external people and
competency/training records are not implemented. Company directory membership
is checked through the existing organization_member_directory function, without
new SECURITY DEFINER functions or broadening permission/grant visibility.

## Contract and invariants

Migration0044 follows0043. The reserved0041 draft stays outside this Alembic chain.
qms_audit_team_members has forced RLS, a composite audit/company/unit foreign key,
an active-person unique index and no runtime DELETE/TRUNCATE permissions.
Read requires audits.read; create/edit/withdraw also requires audits.manage in
that unit. A seat or company role never implies this authority.

| Method/path below `/internal-audits/audits/{audit_id}` | Behavior |
| --- | --- |
| GET `/team-members` | Active/former/all assignments, bounded limit1–50/offset |
| POST `/team-members` | Person, role, responsibilities; expected audit version |
| PATCH `/team-members/{team_id}` | Role/notes and expected audit/assignment versions |
| POST `/team-members/{team_id}/withdraw` | Reasoned retirement using both versions |

Writes return `{member, audit_version}`. CSRF/session and same-origin proxy checks
remain in force. Parent lock/version and draft/planned state are required.
Each assignment change advances parent+member versions and appends one
internal_audit.updated event in the same transaction. Event fields include member
and person IDs, role/version/status, plus hashes of name/notes/reason.

Person ID and display-name snapshot are immutable. A new assignment captures
its name from the authorized directory; clients cannot supply or forge it.
Historical names remain available after membership is revoked. Retirement of an
inactive target is allowed while the parent is valid for planning; the current
actor still needs their own active authority. Terminated parents and withdrawn
assignments are immutable. Downgrade refuses any team row/event history.

## UX and demo

Scheduled audits → select audit → Audit team. Active/former assignments have
paging and show the recorded name, responsibilities, role and version. The lead
badge derives from the parent field, without a second editable lead role.

Add-person uses real company-directory search/paging (search,limit,offset), pins
selection across pages/search and validates UUID before submitting. Editing keeps
the assigned person fixed; retire/create to change identity. The directory is
not exposed through this editor without planning authority. Response context,
identity and versions are validated before acceptance.

409 requires explicit refresh of full parent state. Unknown success/network
outcomes lock blind replay;503 preserves the draft without automatic retry.
401/403/404 closes cached planning context. Old/unmounted requests cannot
repopulate another unit. Existing light/dark tokens and responsive controls are
reused; no library or visual-only business/permission change was introduced.

The development seed adds one planned auditor using the existing demo lead,
through real API commands. It reads every history page, does not duplicate,
resurrect or overwrite assignments and grants no new permissions. Two seed runs
and authorized readback confirmed one demo assignment, alongside the program,
audit, scope and criterion. Independence remains pending.

## Recovery and verification

- Initial source/Git checkpoint recorded in CHECKPOINT.md: encrypted outside the
  working tree, every source hash and Git bundle restored/verified.
- Separate pre0044 database recovery from0043:52tables/46forcedRLS restored in
  isolated tmpfs/network-none PostgreSQL. Post0044 recovery:53tables/47forcedRLS,
  complete content/schema/owners/ACL/role/sequence checks PASS. Actual IDs are in
  CHECKPOINT.md/manifests; ciphertexts and separate0600 keys remain outside Git.
- Source image was unavailable; PostgreSQL executables matched fallback SHA256.
  Only equivalent constant varchar-array deparser casts and built-in pg_*
  bootstrap grantor names were normalized; custom grants/rows fully compared.
- Local migration was explicit0043→0044 after pre-migration recovery PASS. Previous
  images tagged before-audit-team-20261112 retained. Image rollback alone does
  not reverse database history; prefer reviewed forward fixes or isolated restore.
- 43 PostgreSQL audit cases PASS (31previous+12team); empty upgrade/downgrade and
  populated-history protection PASS. Includes no implied execution grant,
  leader/auditee conflicts, immutable snapshots, inactive-person retirement,
  duplicate active persons, company/unit denial, revocation and direct SQL guards.
- 199 process/risk/document/NCR/CAPA integrations PASS with0044; protected CAPA
  downgrade PASS. API format/lint/mypy64 files and50unit PASS;340integrations skip
  in the default runner lacking their harnesses;43+199 actually ran separately.
- Web lint/typecheck/build and60unit PASS; Linux97/97 and Darwin10/10 PASS,
  no retries or golden updates.375/1440 forms pass axe A/AA/reflow in both themes,
  actual screenshots inspected. Ten new browser cases intercept
  every QMS mutation; persistent API seed and live proxy read are separate proof.
- Initial DB test missed setting actor context before direct SQL (UPDATE0 under
  RLS); corrected without weakening the assertion. Revoked test identity is now
  restored in finally, avoiding a leak into the next fixture. Final43-case run PASS.
- No dependency added. Security-tool scope and final counts recorded in checkpoint;
  scanner/axe success does not prove production security or complete WCAG compliance.

PR33/4de65f0 quality43361806578 and CodeQL43361806566 PASS. Security43361806911
failed only Enforce final release gates; the runtime step passed. Do not treat
that as production approval or transfer its PASS to this new head. Independent
review, exact-head CI and human approval remain required. No merge/deployment.

## Remaining audit work

Agenda, reviewer independence, readiness, execution/evidence/findings and
finding-to-NCR/CAPA/Action Center integration remain pending. Reference the
architecture target and Odoo gap review; a planned team is not a finished audit.

Final source/Git/visual checkpoint: **CP-AUDIT-TEAM-06-20261113T042304Z**. Public manifest
records source restoration/bundle integrity and actual evidence hashes.
