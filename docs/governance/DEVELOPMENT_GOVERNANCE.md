# Development Governance

Changes follow: issue, feature branch, implementation, focused validation, full
checkpoint, pull request, review, Product Owner approval, and merge.

No contributor may force-push published history, delete `main`, merge their own
pull request, or close the primary mission issue without authorization. The one
empty-repository exception permits a governance-only base commit to `main`.

Branches use the `pmc/` namespace. Every checkpoint must be evidence-driven;
missing evidence is reported as PARTIAL, never inferred as PASS.

Scope is mission-bound. AWS provisioning, customer data, production credentials,
Odoo access, and unreviewed restrictive dependencies are prohibited during PMC-00.
