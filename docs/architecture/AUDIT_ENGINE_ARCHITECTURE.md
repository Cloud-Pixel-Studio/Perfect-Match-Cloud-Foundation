# Audit Engine Architecture

The Audit Engine is application audit-trail infrastructure, not an ISO Internal Audit module. Every supported business mutation records its event through `pmc_api.audit_service.record` in the caller's PostgreSQL transaction. The event is visible only after that transaction commits; an append failure rolls the mutation back.

The service owns the action vocabulary, actor snapshot, request correlation, payload validation, deterministic changed fields, and resource identity. There is no public audit write endpoint and no background or eventual compliance append path.

The current 0.3.0 vocabulary contains `auth.tenant_selected`, representing a validated active membership and the destination application session. Future actions require a schema-compatible migration and focused integrity tests.
