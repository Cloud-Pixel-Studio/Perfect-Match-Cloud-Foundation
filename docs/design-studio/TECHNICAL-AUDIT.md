# AI Design Studio technical audit

Audit date: 2026-11-11. Branch: `codex/ai-design-studio`. Verified baseline:
short commit `e43d648` (the full identifier remains in Git and the checkpoint).

## Verified foundation

- Frontend: Next.js 16, React 19, TypeScript 6, Inter Variable, Lucide and the
  in-repository design tokens. No second UI library is required.
- The API uses FastAPI and SQLAlchemy/Alembic with PostgreSQL forced RLS.
  Identity is Keycloak OIDC; QMS authority is independent from seats/roles.
- Storage: private S3-compatible SeaweedFS with ClamAV scanning is already used
  for controlled documents. A future media service can reuse the storage
  boundary only after it receives its own object prefix, policies and lifecycle.
- Visual QA: Playwright, screenshot baselines and axe already exist. The new
  renderer uses the pinned Playwright dependency and loopback-only execution.
- Branding: the approved working territory is **Aligned Evidence**. Logos,
  raster variants, tokens, light/dark behavior and brand guidance already exist.
  They are preserved rather than replaced.

## Existing assets reused

- Master logos under `apps/web/public/brand/selected/`.
- Inter and semantic tokens in `packages/design-system/tokens.css`.
- Synthetic workspace screenshot from the verified Darwin visual baseline.
- Existing brand rules in `docs/branding/`.

## Risks found

1. Generation providers can receive prompts and image inputs. Customer data,
   confidential evidence and production screenshots must be blocked before a
   provider call, not merely removed after generation.
2. Provider credentials must remain in a host-side secret boundary. They must
   never enter an agent sandbox, browser bundle, prompt, job log or Git history.
3. A generated image can invent UI, metrics, clients, certification marks or
   standard text. Product mockups therefore require real synthetic screenshots,
   exact copy and a factual-disclosure check.
4. An asset needs tenant ownership, provenance, model/provider version, cost,
   SHA-256, classification, approval state and immutable versions before it can
   become a reusable SaaS record.
5. The current `BrandMark` component uses an inline size attribute. Under the
   repository CSP, inline styles can be rejected. The Design Studio renderer
   avoids that path and uses nonce-compatible stylesheets and intrinsic image
   dimensions.
6. External repositories are separate products or skills with large dependency
   and provider surfaces. None is safe to embed indiscriminately.

## Current implementation boundary

Implemented now: six real PNG deliverables, two original generated backgrounds,
a deterministic browser renderer, a versioned Brand Kit, a safe brief contract,
controlled job-state helpers, a visual gallery and five least-privilege agent
roles. No provider credential, autonomous publication, backend job queue or
customer-data upload was enabled.

Not yet implemented: tenant-persisted design jobs/assets, private media object
policies, provider adapters, cost ledger, asynchronous workers, approval API and
publication connectors. These remain blocked until a dedicated service threat
model and database migration receive human review.

