# Audit Immutability Model

The runtime role receives only `SELECT, INSERT` on `audit_events`; UPDATE, DELETE, and TRUNCATE are revoked. Forced RLS and a database trigger reject UPDATE and DELETE attempts. The migration owner and database administrators remain a trusted administrative boundary. This is database append-only protection, not a cryptographic WORM claim.

Deferred work: WORM/object-lock storage, signed exports, retention automation, SIEM forwarding, and external anchoring require a separately approved design.
