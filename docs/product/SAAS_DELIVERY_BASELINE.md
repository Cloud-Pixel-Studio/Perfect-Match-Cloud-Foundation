# SaaS delivery baseline — 2026-10-26

## Product contract

One complete QMS per customer tenant, sold with user seats. ISO standard profiles
and supported editions are the commercial addons. Functional QMS modules are not
separate paid tiers. Tenant entitlements never replace user authorization.
Pricing, external-user seat rules and billing provider remain undecided.

The public product catalog and customer account must distinguish available,
contracted and planned capabilities. No fabricated compliance badges or enabled
checkout for unvalidated products. Edition changes preserve prior evidence and
mapping versions. Standard publications and certification are not included.

## Architecture recommendation

Keep the existing modular application: Next.js/React/TypeScript frontend,
FastAPI/Python service layer, SQLAlchemy/Alembic and PostgreSQL, OIDC identity,
private S3-compatible storage, Docker and GitHub Actions. This preserves the
implemented identity, audit and organization boundaries. There is no evidence
that rewriting in another framework would improve product security.

Backend services own authorization, QMS transitions and commercial entitlements;
the browser cannot grant them. PostgreSQL RLS is defense in depth with a limited
runtime role, not a replacement for business permissions. Separate migration and
runtime credentials. Keep domain modules in one deployable API initially rather
than introducing distributed services before needed.

Keycloak and SeaweedFS are the current local integrations, not a final production
hosting decision. Validate supported versions, dependency advisories and restore
procedures before each release. Existing version pins are not proof of safety.

## Functional parity inventory

Source: Odoo deployment/customer/modules.txt read on 2026-10-26, blob
886a9056e44abf2ddc96b09264cf3bf82f4d528f. This inventory maps modules, not complete
behavioral parity; inspect models, workflows, ACLs and tests before implementation.

| Odoo reference | SaaS target | Observed status / required acceptance |
| --- | --- | --- |
| pm_qms_core | Organizations, processes, controls | Organization subset exists; processes/controls and scope tests pending |
| pm_qms_documents | Controlled documents | Pending; release authority, revisions and immutable approved versions |
| pm_qms_evidence | Evidence | Pending; private files, scoped retrieval and review history |
| pm_qms_risk | Risks/opportunities | Pending; treatment, ownership and historical assessments |
| pm_qms_ncr | Nonconformities | Pending; containment, correction and closure authority |
| pm_qms_capa | CAPA | Pending; root cause, approval and effectiveness |
| pm_qms_audit | Internal audits | Pending; independence, findings and NCR links; event audit is distinct |
| pm_qms_kpi | Objectives/KPIs | Pending; historical measurements, scoped summaries; inspect supplier behavior |
| pm_qms_management_review | Management review | Pending; fixed input snapshots and follow-up |
| pm_qms_implementation | Guided implementation | Pending; projects, activities and readiness |
| pm_qms_pack_quality | Proprietary methodology | Pending; versioned definitions and controls |
| pm_qms_iso9001 | ISO addon | Pending; versioned references/mappings and entitlement enforcement |
| pm_qms_migration | Import/migration | Pending; validate, preview and audit imports without crossing tenants |
| pm_qms_people | People/training | Pending; competencies, training and scoped personnel records |
| pm_qms_calibration | Equipment/calibration | Pending; out-of-tolerance impact and authority |
| pm_qms_license | SaaS entitlements | Redesign as tenant subscription + seats + ISO addons; not offline license copy |
| pm_qms_app | Product shell | Identity/organization UI exists; QMS dashboard/navigation pending |
| pm_qms_customer_quality | Customer quality | Pending; complaints, satisfaction and performance |
| pm_qms_action_center | Action center | Pending; scoped aggregation and source access checks |
| pm_qms_cost_quality | Cost of quality | Pending; traceable calculations and scoped totals |

Supplier quality is required by the reference README but is not a separately
named addon in this manifest. Locate its models and tests before assigning scope.

## Security acceptance baseline

Preserve Odoo control outcomes, replacing its ACL/record-rule mechanisms with
server permissions, scope checks and tenant RLS. Every requirement needs an owner,
test, evidence SHA and unresolved-risk disposition.

| Boundary | Required evidence before release |
| --- | --- |
| Tenant isolation | Read/write/delete/export/file/search/background-job cross-tenant denial |
| Identity | OIDC validation, session expiry/revocation, CSRF and MFA policy tests |
| Roles and scope | No self-elevation; empty scope denies; direct API and summary access tests |
| QMS authority | Approval, closure, independence and segregation-of-duty negative tests |
| Integrity | Immutable released records, snapshots, historical versions and audit atomicity |
| Commercial access | Concurrent seat allocation, duplicate event handling, forged entitlement rejection |
| File handling | Type/size validation, malware handling policy, private download authorization |
| Web security | CSP hardening, headers, injection defenses and authenticated security testing |
| Supply chain | SAST fixtures, secrets/history scans, dependency/image audits and SBOM tied to SHA |
| Operations | Tested backups/restores, defined RPO/RTO, incident response and restricted support access |

Keep existing checkpoint rule: no unresolved confirmed HIGH/CRITICAL findings;
MEDIUM findings require triage. Scanner presence is not proof of a passing gate.
Review whether third-party image scans and ZAP findings actually block release.
Local inline-script CSP exceptions must not silently become production policy.

Use ISO/IEC 27001:2022 for the ISMS scope, NIST CSF 2.0 for risk outcomes and
OWASP ASVS 5.0.0 for application verification. Proposed technical target: ASVS
Level 2 with risk-selected stronger controls; not a verified claim. Exact control
IDs, applicability, organizational owners and evidence remain to be mapped.

Official references reviewed 2026-10-26:
- https://www.iso.org/standard/27001
- https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20
- https://asvs.owasp.org/
- https://fastapi.tiangolo.com/tutorial/security/
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html

## Delivery sequence

1. Reproduce local runtime and baseline gates; resolve tool/version prerequisites.
2. Review PMC-04 PR #12 and CI; owner controls its merge under repository policy.
3. Detail document/evidence parity and implement one secure end-to-end flow on
   the accepted workflow foundation before extending the remaining QMS domains.
4. Implement tenant subscription, seats and ISO entitlement services alongside
   the catalog/account experience. Select payment provider before live billing.
5. Complete domain parity, regression and recovery evidence before sale as a
   complete QMS. Milestone demos do not imply commercial readiness.

Visual direction: restrained enterprise UI, consistent typography and spacing,
clear tables/statuses, accessible keyboard operation, responsive layouts, and
explicit loading/empty/error states. Security remains enforced outside the UI.

## Local checkpoint: PARTIAL

Code obtained from main 889a5f12e48104a9a612646063035525a8f0dabd into this workspace.
No runtime or tests executed. Node v22.19.0 found; .nvmrc requests 24.20.0. Docker,
pnpm and uv were not found on PATH. No Docker application found in /Applications.
No tooling installed or production deployment attempted. PR #12 remains open at
e2cdff8abc8781e6f3e246abec08d1db8f2540ea; its implementation has not been approved
by this baseline. This change establishes requirements and does not add QMS code.
