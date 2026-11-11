# AI Design Studio architecture

## Target boundary

```text
Perfect Match QMS web
  -> tenant-scoped Design API
      -> brief/classification policy
      -> immutable job + cost ledger
      -> provider adapter (host-side credentials)
      -> isolated worker without customer-network access
      -> private media quarantine prefix
      -> malware/format/metadata checks
      -> Visual QA report
      -> human approval
      -> versioned approved asset registry
      -> separately authorized publication connector
```

The generation worker is not part of the QMS API process. It receives a bounded
job envelope, short-lived object references and no database credential. Provider
adapters implement a common contract and disclose model/version, request ID,
input/output hashes, latency and billed cost.

## Required persisted records

- `design_brand_kits`: tenant, version, token snapshot, approved status.
- `design_jobs`: tenant, requester, type, classification, state, provider,
  model/version, estimate/actual cost and timestamps.
- `design_job_inputs`: immutable hashes, safe-input classification and retention.
- `design_asset_versions`: object key, dimensions, format, SHA-256, provenance,
  disclosure and supersession relationship.
- `design_reviews`: independent QA/human decision, reason and timestamp.
- `design_publications`: destination, approved asset version, idempotency key and
  result. Publishing is a later connector and never an implicit job transition.

Every table requires forced RLS and composite tenant foreign keys. Reading or
writing an asset must require both membership and an explicit Design Studio
capability. Seats and tenant roles must not imply creative approval or publication.

## Security gates

1. Classify before generation; reject customer, confidential and restricted data
   for external providers.
2. Strip EXIF and active content, validate magic bytes, dimensions and decompression
   limits, scan uploads and place outputs in quarantine.
3. Use provider allowlists, egress allowlists, timeouts, size/cost ceilings and an
   idempotency key. Never log prompts containing sensitive content.
4. Treat model output as untrusted. Re-encode media, scan it and prevent SVG/script
   execution before preview.
5. Require independent Visual QA and a human decision before approval. Publication
   needs a second explicit capability and connector-specific confirmation.
6. Retain immutable provenance and cost events; asset replacement creates a new
   version rather than overwriting an approved file.

## Implemented proof

The current branch implements the safe deterministic portion only:

- Brand Kit JSON and five agent role contracts.
- Brief classification and controlled state-transition tests.
- Six exact-size marketing assets rendered locally by Playwright.
- Real product mockups sourced from a synthetic visual regression capture.
- A `/design-studio` gallery with explicit disclosures.

This proof does not claim that tenant-persisted generation, provider integration,
automatic QA or publication is already available.

