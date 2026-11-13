# Audit execution-access diagnostic —13November2026

## Delivered boundary

Migration0047 follows0046. Reviewers can now see whether **every active planned
auditor currently has explicit audits.read AND audits.execute in the audit's
company and unit**, with an active local user and membership. Auditees and
withdrawn assignments do not count. An empty auditor roster is blocked.
Assignment, ownership, a seat, independence assessment or a platform role never
grants execution access. No new capabilities, DB roles or demo grants are created.

GET `/internal-audits/audits/{id}/independence` adds `execution_authority`:

| Actor/result | status | planned_auditors / authorized_auditors |
| --- | --- | --- |
| audits.read without audits.review | unverified | null / null |
| read+review; all planned auditors authorized, nonempty | passed | total / total |
| read+review; empty or partly authorized team | blocked | total / authorized |

The matching preparation check uses the same status. Only counts are returned;
no new endpoint reveals anyone else's grant rows. `can_review` retains0046's
independent segregation rules; a reviewer on the team can inspect counts but
cannot attest their own independence. The response is `Cache-Control: private,
no-store`, verified over the actual web proxy. A revocation between initial
eligibility and the getter returns403 rather than an internal server error.

These are point-in-time diagnostics, not a persisted authorization or a command
precondition reusable later. **ready_for_execution remains literally false**.
Auditor competence records, ready/start transitions, audit evidence, findings
and finding→NCR/CAPA remain unimplemented. Future write commands must revalidate
authority and competence atomically; a passed display is insufficient.

## Database and security boundary

Existing qms_access_grants FORCE RLS and its direct row visibility are preserved.
The runtime cannot inspect other members' grants through the existing policies.
Instead a private, derived projection mirrors only read/execute grant identity
and active/revoked status. Backfill temporarily removes FORCE on the original
inside transactional DDL, then restores it before commit. The ALTER lock spans
the transition. No application traffic sees a committed relaxed source table.

The projection has RLS ENABLED, **NO FORCE and no policies**. PUBLIC and
pmcloud_app have no direct privileges. Accidental runtime SELECT grants still
return no rows. Trusted migration ownership bypasses RLS only inside the narrow
getter. Its trigger runs within the grant transaction, so revocation and rollback
cannot independently commit a stale projection. Grant identity is immutable in
the existing source rules. Projection rows cascade only from original grant
removal; runtime source grant deletion remains forbidden.

`qms_audit_execution_authority(uuid)` is STABLE SECURITY DEFINER, with fixed
pg_catalog/public search_path and schema-qualified tables/functions. It accepts
one audit ID, requires current company plus read+review in its exact unit, and
returns exactly two counts. Unknown, foreign and forbidden IDs all reject42501.
PUBLIC EXECUTE is revoked; pmcloud_app may call only this scoped getter, never
the synchronization trigger. No dynamic SQL, actor switching, global listing,
new DB roles or expanded detailed-grant visibility is introduced. The local
membership projection is the same established private directory source.

This increases the SECURITY DEFINER surface and requires independent security
review and human approval before merge. Runtime must not own the getter or have
CREATE on public, role escalation, or migration credentials. Tests check these
boundaries; they do not certify the entire application or infrastructure.

## Interface and validation

The preparation panel displays counts for eligible reviewers, retains its open
state while refreshing, and uses a skeleton while data reloads. Read-only actors
see unverified without totals. Invalid totals, impossible passed states and a
mismatch between aggregate/check statuses reject the snapshot. No execution
button or workflow state was added. Existing independence history stays intact.

Database proof:91 audit integration cases (16 new) and199 process/document/risk/
NCR/CAPA cases passed in disposable PostgreSQL. Cases cover revoke, rollback,
member/user inactivity, wrong unit/company, empty team, partial team, direct SQL,
raw grant nonvisibility, temporary-table shadowing, private projection ACL/RLS,
review-revocation race and populated0047→0046→0047 reconstruction. Protected
history still blocks destructive older downgrades. The process harness's explicit
TRUNCATE lists include the derived FK table; the QMS grant harness reset does too.
Application constraints are retained. Additional regression:23 QMS access and27
tenant-isolation cases PASS. Its existing QMS downgrade guard rejects retained
event history via the older event constraint; no stronger guard claim is made.

Browser validation and final checkpoint identifiers are recorded in CHECKPOINT.md.
Five new browser cases use intercepted access snapshots; a sixth signs in as the
actual synthetic reviewer and reads the seeded audit without QMS writes. Responsive
375/1440px, light/dark and axe AA checks are scoped evidence, not full WCAG conformity.

A real transport assertion found missing no-store; the API now supplies it, rather
than relying on Next's dynamic route. Earlier failed test/setup runs are retained
in the encrypted evidence archive and are not counted as accepted final results.

## Recovery and remaining risks

CP-AUDIT-AUTHORITY-00-20261113T144345Z restores470 source files plus Git. PreDB
CP-AUDIT-AUTHORITY-DB-00-20261113T144349Z restores0046/55 tables/49 forced RLS.
PostDB CP-AUDIT-AUTHORITY-DB-06-20261113T151525Z restores0047/56 tables/49 forced
RLS. The additional private table intentionally is not forced as described above.
Encrypted dumps and separate0600 keys remain outside Git; no customer dump or
production secrets are committed. Restore ran isolated without network/ports on
tmpfs, comparing rows, schema, custom ACL, roles and sequences. The fallback image
has identical postgres/pg_dump/pg_restore executable SHA256, not an identical image.
Only equivalent constant varchar-array casts and builtin pg_* bootstrap grantor
names are normalized. Before-authority API/web images are retained locally.

The0047 downgrade removes only derived data/functions and can rebuild from grants;
source grants, planning and review history survive. This roundtrip was tested only
in disposable DBs. Do not downgrade a working environment casually or apply the
reserved0041 draft. No production migration, merge or deployment was performed.

No dependencies added. Fresh JS audit still has one pre-existing Moderate advisory
and no High/Critical. PR36 quality and CodeQL passed, but security43435849967 failed
the final release gate; earlier scanner/runtime/ZAP steps passed. Those results do
not certify this new head. Vendor/infrastructure release blockers and deployment
readiness remain separate pending work.

Independent read-only agent review of the0047/API/UI diff found no blocking
finding. It checked source grant immutability, scoped authority, RLS/ACL,
search_path, atomic projection updates and the91-case evidence; it did not run
SQL or mutate files. This bounded review does not replace final-head CI or human
merge approval. No separate infrastructure/pentest result is claimed.

Visual inspection of the1440px light and375px dark captures found consistent
existing styling and no horizontal overflow. Audit detail still requires excessive
vertical scrolling across scope/criteria/team/agenda; this is existing UX debt,
not a completed premium redesign. Consolidating that detail is a next UI task.
