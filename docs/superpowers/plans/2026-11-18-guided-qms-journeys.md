# Guided QMS journeys — first operational delivery

User request: every customer case needs a guided step-by-step view of existing implementation, gaps and the next action. Reuse Odoo readiness ideas, improve clarity for the independent SaaS, preserve work and authorization. Autonomous execution already requested by the user.

Goal: a working **Implementation guide** workspace with six journeys (initial, improve, transition, migrate, audit, expand), ordered instructions, rationale, expected output, completion criteria, existing scoped record observations, next actions and explicit product gaps. This delivery reads existing persisted business records; it does NOT invent a global project, normative assessment, certification, importer, saved completion checkbox or percentage. Formal project/evidence linkage and human review remain separate future work. Presence of records is never reported as a completed phase.

Architecture: existing Next/React/tokens and identity proxy; no backend/DB/auth/licensing/dependency changes. First delivery places the global guide in owner/admin coordination navigation; contributors keep their existing assigned work. Navigation visibility grants no QMS record access: every read obeys the selected unit's effective capabilities and server authorization. Preserve unrelated generated AGENTS. Same tenant/actor keys, abort and post-read identity validation prevent previous-company snapshots. Scope is an organizational unit, not a whole enterprise certification scope.

## Shared contracts / ownership

Root owns `src/lib/guided-journeys.ts` + `.test.ts`, navigation/shell integration, browser regressions, docs/checkpoint, release. Data worker owns `src/lib/guided-journey-data.ts` + `.test.ts`. UI worker owns `src/components/guided-journey-workspace.tsx` and new `src/app/guided-journeys.css` ONLY (root imports CSS). No worker stages/commits others' files or operates VM/secrets.

Data exports:

```ts
type GuideResource = "processes" | "documents" | "implementations" | "risks" | "nonconformities" | "capas" | "audits";
type GuideUnit = { id: string; code: string; name: string };
type GuideRecord = { id: string; code: string; name: string; state: string; qualified: boolean };
type ResourceObservation = { kind: "loaded"; records: GuideRecord[]; limited: boolean } | { kind: "restricted" | "unavailable" };
type GuideSnapshot = { tenantId: string; userId: string; unitId: string; fetchedAt: string; resources: Record<GuideResource, ResourceObservation> };
class GuideAccessError extends Error { status: number }
loadGuideUnits(tenantId: string, signal?: AbortSignal, request?: typeof fetch): Promise<{units: GuideUnit[]; limited: boolean}>;
loadGuideSnapshot(context: {tenantId: string; userId: string; unitId: string}, signal?: AbortSignal, request?: typeof fetch): Promise<GuideSnapshot>;
```

Catalog exports `journeys: GuideJourney[]`; `GuideJourney={id: "initial"|"improve"|"transition"|"migrate"|"audit"|"expand"; title:string; summary:string; outcome:string; steps:GuideStep[]}`; `GuideStep={id:string; title:string; why:string; instructions:string[]; expected:string; doneWhen:string; resource?:GuideResource; workspace?:WorkspaceId; productGap?:string; limitation?:string}`. No persisted statuses in these definitions. Both catalog and data module may refer to data-exported types; data has no dependency on catalog.

UI props: `{tenantId:string; userId:string; preferredUnitId?:string; onUnitChange?:(unitId:string)=>void; onNavigate:(id:WorkspaceId)=>void}`. Unit selector, six case cards, step list/detail, previous/next; snapshot refresh and permission-aware open-module buttons. Labels **Records found**, **No records found**, **Access required**, **Could not verify**, **Feature pending**; qualified record state is described specifically, not ISO readiness. Limited pages must say first50/at least rather than total. Clear evidence before reload/error/context change. No localStorage of business data or fake completion. A guide can be read without unit access, but observations/actions require authorized data/workspace.

## Tasks

- [x] Preserve baseline and inspect Odoo center/next-action logic (read-only specialist).
- [x] TDD data reader: same-origin/no-store/include, unit/tenant integrity, effective scopes, forbidden reads skipped, capped pages, malformed/cross-unit/tenant/duplicate/identity-changed responses fail closed,401/403 invalidates complete snapshot, late aborted requests ignored. Unit list max100 with limited label.
- [x] TDD catalog: all six unique journeys, ordered distinct steps, every step has why/instructions/output/doneWhen, missing-product stages explicitly unavailable, no normative completion or percentages from record counts.
- [x] Build accessible responsive UI using shared contracts, preserving navigation and state across inspection without claiming a saved project. User never marks an entire requirement done by checkbox.
- [x] Integrate workspace and scoped module navigation; root keeps unit preference and actor/company/role remount. Add regression to existing navigation tests; update legitimate visual baselines only after actual review.
- [x] Verify unit suite/lint/typecheck/build; add browser tests for every journey,401/403, missing permissions, sample limits, scope changes and product gaps; CUA local fixture, screenshot proof. Browser CI not executed locally via another browser driver.
- [x] Final checkpoint, secret scan and draft PR66 against scenario comparison. Exact code CI quality/CodeQL success. Isolated demo configuration checkpoint and Linux image prepared; installation held by unpatched picomatch HIGH, no waiver. Six running services unchanged/healthy. Browser CI blocked before runtime, no PASS claimed. No production.

Review focus: counts from whole unit must never complete a project step; draft/accepted/implemented distinctions; zero denominators; stale context; no hidden role-based authority. Guide is operational navigation with current observations, not the full persistent Project QMS engine. Ruling: implement this independently usable slice first — it exposes real progress/gaps safely while the normative and project engines are absent.

Ruling: coordinator navigation is owner/admin for this first global guide, consistent with their company setup responsibility; it never bypasses unit capabilities. Contributor task guidance remains in existing activities. A future persisted project should add explicit project responsibilities rather than treating ownership as normative approval.

Ledger: Odooreadinessreviewfound missing-before-underreviewprecedence andzero-denominator100%; catalogdoesnotreusefalsecompletion. DatareaderRED→GREEN65cases, includingactualdocuments51sentinel. Frontend208suitePASS,lint/typecheck/buildPASS. CUA6journeyswithreal-demo-response-replay,401/403cleared,mobile375inspected;replayloginnotrealOIDC. PendingisolateddemoimageupgradeandfinalPR.

Final visual correction: detail heading focus could hide below sticky topbar (CUA RED); prevent default focus scroll, then immediate scrollIntoView with8rem margin. Responsive browser assertion added. Final local checks and CUA GREEN recorded in handoff.
