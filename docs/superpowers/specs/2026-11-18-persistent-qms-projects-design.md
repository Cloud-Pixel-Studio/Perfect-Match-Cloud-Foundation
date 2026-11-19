# Persistent QMS journey planning

User intent: every customer starting, changing, transitioning, migrating, preparing audit or expanding must follow a guide, resume it and see existing work/gaps. Repeated autonomous implementation authorization applies; the following implementation choices are engineering rulings, not additional user decisions.

## Selected approach

Extend the existing guide with a server-backed project and step planning records using FastAPI/SQLAlchemy/PostgreSQL RLS and existing Next/tokens/proxy. A localStorage checklist would lose audit/context and is rejected. Implementing formal normative approval before reviewed ISO profiles/evidence linkage exist would misstate readiness and is excluded from this independently usable delivery.

Project: selected unit, unique company code, name, journey_key, immutable catalog_version guided-qms-v1, scope_summary, optional coordinator/target date, open/archived status, optimistic row_version, actor/timestamps. Unit and journey immutable. Step plans generated atomically from a fixed server catalog matching the44guide steps. Each retains key/order, optional assignee/date, notes, row_version and status not_started/in_progress/blocked/reported; reported means self-reported work pending separate verification, never accepted evidence or a completed phase. Blocked/reported require meaningful notes. Product gaps retain immutable feature_pending status, may carry planning notes/assignee/date, and cannot be reported implemented. No percentages or verified/completed statuses.

Only explicitly granted projects.read can read; writes require both projects.read and projects.manage for the exact unit. No autogrants, owner bypass, seat authority or changes to existing QMS read authority. Auditors may receive projects.read, never manage. Guide remains discoverable for owner/admin coordinators and additionally for explicit projects.read holders; per-unit APIs still decide all access. Directory validates active company membership; assignee does not gain unit or project access from assignment. UI states that assignment alone grants no permissions.

Every mutation records an immutable audit event in the same transaction; use reason for archive/restore, no DELETE. DB enforcement: FORCE RLS, same-company/unit FK, active scope lock, identity/catalog/version immutability, exact catalog step set, valid member checks and current actor, atomic project version increment for step changes. Competing edits yield409. Archive makes metadata/steps immutable until explicit restore. Empty-only downgrade, preserving grant and audit history; no real DB migration or demo deployment in this delivery.

UI: project list/create/edit/archive/restore within existing implementation guide after unit selection; select project pins journey. Project and step notes persist; scope observations remain separately labeled unit records, not project evidence. Refresh/context/401/403 clears data; responses revalidate actor/company/unit, malformed/cross-scope/old response discarded. Mutation uses existing CSRF proxy, never retry automatically;409 preserves draft and asks refresh/reconciliation. Errors do not show success. Only authorized forms render. Cancel current project returns to guide, no deletion. Frozen catalog mismatch disables project editing with clear message, never silently changes steps.

## Limits

No formal project acceptance, ISO mappings/edition approval, universal importer, project-evidence links, review snapshots, executed audits or automatic completion. No changes to production, demo DB, Odoo dependencies, existing permissions or package versions. Existing picomatch/Keycloak security gates remain enforced; upstream patch needed for release.
