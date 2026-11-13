# Focused audit detail —13November2026

## Implemented

The former audit detail stacked scope, criteria, people, agenda, independence and
preparation into one long page. It now presents three task-specific views:

| View | Existing content |
| --- | --- |
| Scope & criteria | Authored scope summary, structured process scope, evaluation criteria |
| People & schedule | Planned auditors/auditees, responsibilities and UTC agenda |
| Readiness | Independence assessments/history, current access diagnostic, preparation checks, recorded conclusion when present |

Code/title/state, objective, dates, lead, version and linked program remain shared
context above the views. Record history and the existing planning commands remain
available below. Programs retain their existing interface. These are presentation
sections, not new workflow stages or a readiness score. Missing competence,
ready/start, evidence and findings are still unavailable; execution remains blocked.

`AuditDetailSections` owns only the active view. ARIA tab/panel relationships,
roving tabindex, horizontal Arrow/Home/End keyboard navigation and visible focus
are implemented. Three columns wrap labels within mobile width, with44px minimum
height. Existing semantic tokens provide light/dark/selected/disabled styles;
reduced motion respects the shared system's0.01ms limit. No dependency or extra
component library is introduced.

## State, permissions and API preservation

All five original domain components stay mounted in their respective panels.
Native hidden plus explicit display:none removes inactive content from presentation
and the accessibility tree while preserving in-memory drafts, paging and local
validation. Selecting a view does not submit a form, write QMS data, change parent
version or refetch its data. This is deliberately not lazy loading; existing scoped
reads and their access-invalidating callbacks still run even for hidden sections.

The wrapper is keyed by audit ID. Unit/organization changes and loss of access
continue to remove the parent context; they do not carry a hidden form across a
company/unit/audit boundary. A refresh retains the previous established lifecycle.
All section buttons are disabled during a pending command and during a shared
planning editor/transition. Nested editors may be revisited without discarding
their drafts, exactly as preserving mounted editors requires. Existing API
optimistic concurrency, authority and CSRF behavior remain unchanged.

No backend, schema, authentication, authorization, license, business transition,
API contract, dependency or production infrastructure was changed. The new tabs
are navigation only; they must never be treated as an access boundary.

## Validation

Six new browser cases cover keyboard/one-visible-view semantics, a draft surviving
navigation and saving exactly once against its original plan, tabs disabled while
a write is pending, hidden draft cleanup after unit change, responsive/theme/axe
checks with reduced motion, and a live seeded audit reviewed through the real
web proxy with no QMS writes. Existing team, agenda, independence and live-demo
cases explicitly navigate to their sections before interacting; assertions and
API field/version checks remain intact.

The visual matrix covers375/768/1440px, both themes and all three views, with no
horizontal overflow, bounded selected-panel height and scoped axe AA checks. It
produces12 canonical screenshots plus a separate real-demo capture. These checks
are not a complete WCAG certification. Existing screenshot baselines continue to
run without golden updates. Final counts and checkpoint evidence are recorded in
CHECKPOINT.md after the full regression completes.

Independent read-only UI/security review found no blocking issue in ARIA/focus,
mounted drafts, busy guards, context cleanup and original capability callbacks.
The reviewer read the focused6/6 PASS log but did not inspect screenshots or mutate
files. Root visual inspection covered desktop Scope & criteria/light and mobile
Readiness/dark; full screenshot metadata is preserved with evidence.

## Recovery and next work

CP-AUDIT-DETAIL-00-20261113T153013Z restored477 source files and Git before edits.
The local preview replaces only the web image; before-audit-detail-20261113 is
retained. API and database remain at0047. No new DB restore is claimed because
this slice does not alter schema/data; the separate verified0047 database restore
from the authority milestone remains available. Backups/keys are outside Git.
Final source/Git/screenshots/reports and the delivered exact-head bundle are
verified separately before/after synchronization.

Remaining: long content within each individual section still scrolls; this is a
navigation improvement, not a complete product redesign. Searchable long audit
registers, people/competence records, execution/evidence/findings and commercial
licensing/billing remain independent future work. Require final-head CI and human
approval before merge; no merge or production deployment is authorized here.

Final local regression:130/130 Linux and6/6 Darwin PASS without retries or
golden updates;60 web unit tests/lint/types/build PASS. The hidden-draft cleanup
assertion was strengthened to inspect the hidden DOM and actual input values;
it is covered by Darwin6 and a separate focused Linux run after the full130.
No backend suite is re-claimed as executed in this UI-only slice. PR37's earlier
340 DB/50 API cases remain historical evidence.

Measured full-page fixture capture heights: desktop Scope & criteria/light is
2575px versus the former4772px (46.0% shorter); mobile Readiness/dark with checks
expanded is3877px versus6850px (43.4% shorter). Baseline images match the previous
authority checkpoint SHA256. These are specific fixture comparisons, not a
product-wide usability or performance metric. More vertical simplification remains.

Base PR37/012ba4b CI: quality43452520965 and CodeQL43452520777 PASS. Security
43452521063/job131978090519 FAIL only Enforce final release gates; preceding
runtime, visual, scanners, SBOM and ZAP steps PASS. No new-head CI success is
implied, and the release remains blocked. Current JS audit has one existing
Moderate and zero High/Critical; it does not establish container security.
