# Audit Engine Architecture

The Audit Engine is application audit-trail infrastructure, not an ISO Internal Audit module. Every supported business mutation records its event through the single authoritative `pmc_api.audit_service` write boundary in the caller's PostgreSQL transaction. The typed `record_tenant_selected` and PMC-03 organization builders keep action and payload contracts server-owned; the read-only `pmc_api.audit` module cannot construct or persist events. The event is visible only after that transaction commits; an append failure rolls the mutation back.

The service owns the action vocabulary, fixed safe action payloads, actor snapshot, request correlation, defensive normalized secret-key validation, deterministic changed fields, and resource identity. There is no public audit write endpoint and no background or eventual compliance append path.

The current vocabulary contains `auth.tenant_selected` plus the typed PMC-03 organization actions, representing validated active membership and tenant-scoped product mutations. New actions require a schema-compatible migration and focused integrity tests.
