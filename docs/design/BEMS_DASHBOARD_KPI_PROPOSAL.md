# BEMS Quality — Dashboard KPI and analytics proposal

Status: design proposal only. No fabricated tenant data, no backend or production changes.
Base: `codex/product-marketing`. Reviewed `apps/web/src/components/workspace-overview.tsx` and `apps/web/src/components/identity-shell.tsx`.

## Current dashboard
The authenticated Overview uses a tenant/role context hero, `ActionCenterWorkspace compact`, and role-filtered module cards. It is a navigation hub, not yet a consolidated analytics surface. Preserve the current restrained teal/graphite visual language and organization-scoped navigation.

## Proposed layout
1. Keep existing organization and role context, including explicit data freshness and date range.
2. Add a compact KPI row before the Action Center. Responsive: four columns desktop, two tablet, one/two mobile according to width.
3. Keep the Action Center as the primary operational section, with links to source records.
4. Add two analytics panels: six-month NCR/CAPA trend and action aging/status breakdown.
5. Retain module navigation cards beneath the analytics, without losing role-based filtering.

## KPI definitions (not yet implemented)
| KPI | Definition | Source required | Drill-down |
|---|---|---|---|
| Document currency | Released current documents / applicable controlled documents, with explicit exclusions | Document lifecycle and revision status | Documents |
| CAPA overdue | Open CAPA with due date before tenant-local today | CAPA due date and state | CAPA |
| Action on-time completion | Actions closed by due date / actions closed in selected period; show numerator and denominator | Action Center and lifecycle history | Action Center |
| High/critical risks | Active risks with residual rating in configured high/critical bands | Risk register, tenant-configured matrix | Risks |
| NCR opened vs closed | Monthly counts by recorded event date; two series | NCR lifecycle events | Nonconformities |
| CAPA closure trend | Monthly closure count; optionally median days to close when dates complete | CAPA history | CAPA |

Avoid ambiguous percentage claims: disclose denominator, time window, and status inclusion rules. Do not assume ISO certification, audit completion or supplier KPI endpoints exist.

## Data contract proposal
A dedicated authorized read-only `GET /api/identity/dashboard/summary?period=90d` or analogous existing backend route, returning scoped `tenant_id`, `as_of`, `timezone`, `period`, `metrics`, `series`, and `permissions`. Backend must derive tenant from the authenticated session, never trust tenant ID from a client query. Only return aggregated counts for modules authorized to the user; hide restricted cards and avoid count-based information leakage. No cross-tenant caching.

Use explicit states: loading skeleton; no records; insufficient data; partial module permissions; stale; fetch error with retry. Never substitute demo numbers in a live workspace.

## Visual and accessibility acceptance criteria
- Preserve existing CSS variables and dark mode; no new bright gradients.
- Responsive layout at 360, 390, 768, 1024, 1440 px; chart labels and KPI values never clipped.
- Charts have textual summaries and accessible tables; keyboard navigation, visible focus, reduced-motion support.
- Color is never the sole status indicator; overdue indicators include labels.
- Dates use tenant timezone, not device timezone; explain freshness and period.
- Clickable cards navigate only to already-authorized module views.
- Graph data sourced from actual APIs, never hardcoded demo fixtures in production.
- Automated tests for denominators, zero data, role isolation, cross-tenant access, stale API and mobile overflow.

## Implementation phases
A. UI-only layout behind a feature flag with truthful empty/placeholder states, preserving Overview.
B. Backend aggregates and permission-scoped endpoint with tests.
C. Connect cards and charts, add filters and drill-down, verify a11y and responsive.
D. Performance and security checks; deploy only after release gates clear.

No production deployment or KPI endpoint is asserted in this proposal.
