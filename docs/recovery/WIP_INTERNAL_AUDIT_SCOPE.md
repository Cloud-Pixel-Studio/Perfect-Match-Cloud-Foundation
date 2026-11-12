# Internal-audit scope work — recovery snapshot only

Status: UNVALIDATED DRAFT. This branch preserves local work so another chat can
inspect it. It is not the current visual branch and is not ready to merge,
deploy, or apply to any database.

Base: `ad40de02bd077d0a57b920ecb66a4f2bef2212a0`
(`codex/internal-audit-foundation`, PR #16).

Preserved files:
- `apps/api/migrations/versions/0041_internal_audit_scope_team.py`
- `docs/architecture/QMS_INTERNAL_AUDITS.md`

The migration file SHA-256 is
`88daa9c3bd497832a29a8e18d37e640b7d388bf516be666b8f766c963cf6ee0b`.
Python syntax and Gitleaks passed. No migration, PostgreSQL/RLS, API, or workflow
test has validated this draft. No API routes, models, UI or demo data were added
for this slice. Do not run `alembic upgrade head` from this recovery branch.

Next engineering work: review the draft against the documented invariants,
add scoped models and commands, write isolated PostgreSQL/RLS and migration
tests, verify independent review and readiness transitions, then consider a
separate implementation PR. Existing audit planning 0040 is the tested baseline.

The latest visual work and continuation instructions live on
`codex/ai-design-studio` (PR #17), in `CHECKPOINT.md` and
`docs/product/CONTINUE_FROM_HERE.md`.

Original local files remain untouched in the `codex/internal-audit-scope-team`
worktree. No secrets, database dump or customer data are part of this snapshot.
