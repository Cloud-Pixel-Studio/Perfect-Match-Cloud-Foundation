# Independent integration review —17 November2026

## Baseline and evidence

The separate reviewer did not implement the integration. Read-only scope was
bb6bc9cafa8b1c97d94f919346e68aa9e43586d6, effective diff from fa4032e, all36
original PR head ancestries and exact CI evidence. No secrets, customer data or
local demo mutations were involved. This is an independent agent review, not
human approval, certification or a complete fresh audit of every original PR.

The reviewer verified the final ZIP digest, six Trivy report hashes, source/run
binding, five images at0High/Critical and Keycloak at6HIGH. Embedded Playwright
report:158 expected/0unexpected/0flaky/0skipped. Product handlers, RLS and authority
were preserved in the effective integration diff. The new document_control
prototype is isolated, KPI contracts have no live consumers, BEMS is optional,
and the minimal reviewer test now demands success without broadening grants.

## P2: malformed candidate report accepted as clean

Both candidate scan paths used `.Vulnerabilities? // []`. jq also treats boolean
false as a fallback value, so `{Results:[{Vulnerabilities:false}]}` passed the
schema check and counted0 vulnerabilities. This was reproduced using the exact
workflow predicates. The Foundation collector is separately strict; the finding
does not demonstrate a bypass of its actual6HIGH release blocker.

Behavioral regression tests now extract and execute each real jq predicate from
PR and manual scan steps. They reproduced22 rejected-shape/severity failures
before the fix. Additional tests exposed the manual final gate accepting an
empty counts object. Before correction,11tests failed with25 subtest/assertion
failures, including those safety checks; these were not hidden or skipped.

Correction:

- Accept absent/null vulnerability sections or arrays, rejecting booleans,
  objects, numbers and strings; require array entries to be objects with a known
  severity label. UNKNOWN remains a valid scanner label, preserving policy.
- Require both candidate counts to be numeric zero in the manual final gate,
  matching the PR gate; empty/missing counts cannot pass by vacuous truth.
- No severity downgrade, scanner exclusion, vendor substitution or CVE waiver.
- No SaaS backend/frontend, API, auth, permissions, dependencies or DB changes.

Local validation after the correction:11 workflow tests and83 root tests PASS;
12 schema validations against the six real baseline CI reports PASS. Both final
gates still reject the known Keycloak6/Seaweed0 count map. YAML parses and diff
whitespace checks pass. A first root invocation used system Python without
httpx and failed at collection; the existing API venv passed, without dependency
installation. The independent reviewer then re-ran the11 workflow tests and12 validations,
confirmed both gates still reject6HIGH, found no new issues in the bounded fix,
and confirmed application/permission/DB sources were unchanged. This follow-up
review was on the uncommitted fix over bb6bc9c; exact-head GitHub CI is still
required after publication.

## Official vendor/tool recheck

Latest Keycloak remains26.8.2 and official Quay manifest remains
c68e286cacd87b942ac1939a0a1481461109d6acd3a57dc496969a319a76bbf0.
No official correction of the6HIGH blocker was found. Main's required security
gate remains binding; no merge/closure or production deployment performed.

[OpenGrep2.0.0](https://github.com/opengrep/opengrep/releases/tag/v2.0.0) was evaluated
as an isolated official macOS ARM binary; SHA256 matched release metadata and
license is LGPL2.1. It still reports the same partial parse at the two PEP695
function signatures in control_definitions.py. It is not integrated: CI remains
pinned1.29.0, local baseline scanner1.32.0 remains separate, and no backend code
was rewritten merely for scanner compatibility. Zero findings is not full SAST
coverage. Binary integrity comparison is not a claim of signature verification.

## Recovery and disposition

CP-INTEGRATION-REVIEW-00-20261117T140903Z captures700 source/Git files before any
fix. External AES-256-GCM source/Git backups passed decryption, isolated file
restoration/SHA256, Git bundle verification and tamper rejection. No database
mutation or new DB restoration is asserted for this CI-only change.

Original PRs and review discussions remain preserved. Integration must receive
follow-up review and exact-head checks; then the official Keycloak release
blocker must be remediated before the normal integration order can proceed.
