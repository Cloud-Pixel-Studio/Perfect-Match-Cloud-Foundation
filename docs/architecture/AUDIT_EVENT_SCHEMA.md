# Audit Event Schema

`audit_events` contains: UUID `id`; tenant UUID; server-generated `occurred_at`; actor UUID; historical actor display-name snapshot; actor role snapshot; stable namespaced action; resource type and optional UUID; server request UUID; schema version; deterministic changed-field names; sanitized before/after JSON; and sanitized metadata JSON.

Events do not store actor email, client timestamps, raw credentials, tokens, cookies, login codes, PKCE material, or arbitrary client actions. The table uses restricted foreign keys so destructive actor or tenant deletion cannot silently erase history.
