# Security Policy

Perfect Match Cloud uses secure defaults, least privilege, tenant isolation,
defense in depth, secret-free source control, and evidence-based risk treatment.

Future authenticated request flow is identity, trusted tenant context,
authorization, then resource access. Client-provided tenant identifiers are never
trusted when authenticated tenant context exists. PostgreSQL row-level security
is planned as defense in depth.

No proprietary source may be uploaded to external SaaS scanners. No customer or
production data is permitted in local development. Secrets must be supplied at
runtime and never committed.

Confirmed unresolved CRITICAL and HIGH findings block release. False positives
require documented evidence, rationale, scope, and reviewable suppression.
