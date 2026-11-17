# External agent orchestration and API catalogs — evaluation backlog

Status: **research references only**. Adding a repository link does not install, launch, license, or authorize an agent or API. Evaluate against existing Codex specialists in PR #20 and the UX/reliability additions in PR #22.

## 1. Claude Squad — smtg-ai/claude-squad
Source: https://github.com/smtg-ai/claude-squad

Candidate for operator-side parallel coding sessions using isolated git workspaces. Assess compatibility with Codex CLI, terminal/tmux requirements, worktree lifecycle, process supervision, crash recovery, session persistence, observability, CI, sandboxing and token cost. Review AGPL-3.0 obligations with counsel before redistribution or integration. Do not install in the PM QMS production runtime. Do not confuse locally running sessions with a 24/7 unattended service. Prefer a controlled development runner and protected PR flow; no production credentials in agents.

Acceptance gate: disposable development-host proof of concept, two isolated tasks and branches, no overlapping file writes, automated test evidence, graceful restart, resource/cost limits, manual review and security signoff.

## 2. API Mega List — cporter202/API-mega-list
Source: https://github.com/cporter202/API-mega-list

Discovery directory, **not** a verified inventory of production-ready or free APIs. For each proposed integration, independently verify provider ownership, current docs, uptime/SLA, terms, data residency, authentication, rate limits, pricing, privacy, DPA, secrets rotation, least privilege, error handling, auditability and vendor lock-in. Never ingest the entire directory into app dependencies or grant broad access.

Candidate use cases after product requirements: email delivery, notifications, billing, CRM, analytics. Integrations require tenant-scoped authorization, explicit consent where relevant, outbound egress controls and synthetic contract tests.

## 3. Lead Gen API Stack — cporter202/lead-gen-api-stack
Source: https://github.com/cporter202/lead-gen-api-stack

Commercial outreach research **separate from QMS core product and tenant data**. Do not collect or enrich customer audit data for marketing. Evaluate applicable privacy/anti-spam requirements, provider terms, provenance, opt-out handling, consent, retention and data minimization before any integration. No automated scraping, bulk outreach, or unreviewed third-party credentials.

Acceptance gate: independent business use case, legal/privacy review, approved provider, small synthetic pilot, cost ceiling, consent and suppression controls, clear separation from PM QMS production.

## PO decision
P0 remains release security (Keycloak/SeaweedFS vulnerabilities), tenant isolation, identity, migrations and recovery evidence in issue #18. These references are P2 exploratory; **none blocks P0 and none authorizes merge or deployment**. Keep existing max four concurrent Codex threads until an executor is proven. 
