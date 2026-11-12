# Document control and evidence — acceptance draft

The module is partially implemented; this remains its acceptance contract, not a parity claim.
Read against the Odoo models `addons/pm_qms_documents/models/document.py` and
`document_revision.py`, fetched on 2026-10-26. QMS functionality is included in the
base subscription and does not require an ISO addon.

## Functional contract

- Controlled document: tenant, organization/process scope, unique document code,
  title, type, accountable owner, current revision and obsolete state.
- Types: policy, procedure, work instruction, form, record template, manual, other.
- Revisions: unique revision label per document, prepared/reviewed/approved actors,
  timestamps, effective/review dates, change summary and a private file version.
- Revision lifecycle: draft → under_review → approved → active → superseded;
  rejection returns work to an editable revision with review history retained.
- Creating a revision does not replace the currently active revision. Activation
  supersedes the previous revision atomically. At most one revision is active.
- Obsolete documents preserve their revisions and history. A new revision is
  required to change released content. No silent historical deletion or rewrite.
- Link evidence and documents to controls/implementation records when those
  domains exist; do not substitute unvalidated free-text IDs for scoped relations.
- Supplier/customer records and ISO mappings reference the same controlled
  document identity rather than copying independent document versions.

## Required design decisions before coding the domain

1. Model processes and organization/scope assignment explicitly; existing PMC-03
   sites/departments/teams are not the whole Odoo process and scope model.
2. Define tenant-scoped QMS capabilities (author, review, approve, release,
   obsolete) separately from subscription entitlements and platform administration.
   Membership as owner/admin alone must not imply every business approval power.
3. Define approval independence policy. Proposed secure default: preparer cannot
   approve their own revision. This is an intentional strengthening proposal,
   not a claim that the inspected Odoo revision model already enforces it.
4. Pin the generic workflow version while enforcing document-specific authority
   and state rules in the document service. Generic assignment eligibility is
   insufficient to authorize publication.
5. Use explicit composite tenant/document/revision/file/workflow references.
   Never accept a caller-selected tenant or a raw storage object key as authority.

## Security and consistency acceptance

| Scenario | Expected evidence |
| --- | --- |
| Other-tenant ID in read/edit/link/download/export | Denial through API and forced database RLS |
| Empty or unauthorized organization/process scope | Denial, including dashboard/search results |
| PATCH tries state/approver/active-revision override | Rejected; only command handlers transition |
| Author attempts forbidden self-approval | Denied; no state or audit side effects |
| Two activations overlap | Parent document lock + unique active-revision constraint; one consistent result |
| Request preloaded before another transition | Locked record refreshed; stale version returns conflict |
| Audit writer fails | Entire domain transition and workflow mutation roll back |
| Released file/content/dates or scope silently changed | Denied; create a new controlled revision |
| Older revision superseded | Its evidence and approval snapshot remain readable to authorized users |
| Workflow transition targets another revision | Denied by explicit resource linkage and tenant constraints |
| Upload is oversized, mismatched or unscanned | Quarantined/rejected; not releasable or publicly readable |
| Client supplies foreign object key/signed URL | Ignored as authority; server verifies file ownership/scope |
| Revoked membership or changed scope | Download authorization rechecked; signed-URL exposure bounded |
| Import duplicates or cross-links foreign tenant data | Validated preview; fail without partial unsafe writes |

File storage needs size/type restrictions, quarantine/scanning policy, content
hashes, private storage, safe filenames and controlled downloads. Keep content,
tokens and signed download URLs out of audit payloads. Audit stores safe revision
IDs, state transitions, actor identity and request correlation.

## UI acceptance

Document register with code/title/type/owner/current revision/status/review date,
search and scope-aware filters; detail with revision timeline, evidence, review
decisions and only the commands permitted for the current user. Clear read-only,
empty, loading and denied states. Keyboard operation and responsive tables.
Permission enforcement remains on the server even when buttons are hidden.

## Completion gate

Implement migrations/RLS, capabilities, domain/API, file handling and UI together
with the negative and concurrent tests above. Review Odoo ACLs, record rules,
document tests and evidence models before closing parity. The inspected models
alone are not sufficient proof of complete behavior or security equivalence.

## Current delivery status — 2026-10-28

Implemented: migrations `0010`–`0014` for document/revision tables and scoped
API, audit, explicit response
schemas that omit storage object keys, PDF scanning/storage/download controls,
effective-permission API, allowed web proxy root, and initial register/revision
workspace with permission-gated workflow commands. The process picker requires
both `documents.author` and `processes.read`; the server enforces each capability
and the unit scope. Owner selection, bounded code/title search and pagination,
and a separately granted, version-checked obsolescence command are present in
the current code. Migration `0014` enforces an active tenant member as owner
and requires an active, same-scope process at document creation. Both new
migrations passed upgrade/downgrade/upgrade on disposable PostgreSQL and are
applied to the persistent local development DB.
Document register and revision reads now require an explicit scoped document
capability in the API as well as RLS; an authenticated OIDC smoke verified
denial through both API and web proxy for a member without document responsibility.

Static checks pass (Ruff/mypy, ESLint, TypeScript, build). API unit tests: 41
passed, 122 requiring PostgreSQL skipped; web: 8 passed. The disposable
PostgreSQL processes/documents suite: 27 passed. The real local OIDC→API→
PostgreSQL→ClamAV→private SeaweedFS→web proxy flow passed for create, upload,
independent submit/approve/release, integrity-checked download, audit and
obsolescence. Test grants were revoked; the uniquely tagged development record
was retained as obsolete. Full-tree OpenGrep and Gitleaks previously found no
findings/secrets. Browser-driven UI review and visual review remain unverified.
The UI now has code/title search and bounded pagination. Complete review decision
details display the prepared/reviewed/approved actors plus revision, review and
effective dates. Browser usability/visual review and the remaining acceptance
contract are still outstanding.
