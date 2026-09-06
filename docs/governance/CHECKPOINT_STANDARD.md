# Checkpoint Standard

Checkpoint outcomes are PASS, PARTIAL, or FAIL. Each result must cite observed
versions, command outcomes, tests, scans, health responses, repository state, and
known limitations. Counts, findings, SHAs, and synchronization state must never
be estimated or fabricated.

A checkpoint cannot pass when an applicable functional, security, supply-chain,
license, auditability, or UX gate fails. Confirmed unresolved CRITICAL and HIGH
security findings must both equal zero. MEDIUM findings require triage.

Generated evidence belongs in ignored `artifacts/` paths or CI artifacts rather
than source directories.
