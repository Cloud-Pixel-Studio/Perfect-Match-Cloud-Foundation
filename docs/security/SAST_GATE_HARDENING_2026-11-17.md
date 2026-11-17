# Blocking SAST gate and parser compatibility —17 November2026

## Problem reproduced against the pinned scanner

The exact Foundation command lacked both `--error` and `--strict`. Official
OpenGrep1.29.0 returned exit0 despite one synthetic authentication-bypass finding.
It also returned0 while its SARIF contained a real partial-parsing warning for
control_definitions.py. The prior source-bound artifact14337143936 confirms the
warning; its SARIF executionSuccessful=true did not establish complete parsing.

Five new regression tests extract and execute the real CI and local-checkpoint
commands. They check finding→1 with retained SARIF, clean→0, reported parser
warning→3, and fixture-checker treatment of scanner failures. Before correction,
the tests failed with6 subtest failures; afterwards all5 PASS. The warning
fixture is valid Python3.12 with the pinned parser's known unsupported signature
and safe anchors that engage its rule prefilter. This tests reported warnings;
it does not claim a scanner diagnoses every possible invalid program.

## Implemented changes

- CI and local checkpoint now use `--error --strict`. Findings and reported WARN
  diagnostics block completion. SARIF remains available as failure evidence.
- Positive rule fixtures must exit exactly1. Configuration/parser/internal
  failures2/3 cannot masquerade as expected detections. Negative fixtures must
  still pass. Regression tests use conditional fake scanner failures to prove
  that distinction, plus the actual pinned scanner on clean/finding/warning code.
- Local source scope now follows CI's `.gitignore` policy instead of recursively
  scanning ignored generated toolchains/builds. No Python versioned in the
  reviewed baseline matched `.gitignore`; rules and maintained source are not
  excluded. Dependencies still have their separate release scans.
- Two private generic helpers use a bounded TypeVar instead of PEP695 function
  parameters. The union bound and input/return type relationship remain intact.
  This removes the concrete parser gap without upgrading scanner dependencies.

The two local `noqa: UP047` comments suppress only Ruff's modernization/style
recommendation. No security rule, finding severity or CVE is suppressed. Remove
that compatibility accommodation when the pinned scanner demonstrably supports
these signatures. Private typing metadata changes; no consumers of
`__type_params__` were found. Public endpoint/model ASTs and all function bodies
are identical. The independent reviewer normalized only private typing and its
import/declaration and found the remaining AST identical.

## Validation and boundaries

- Pinned OpenGrep1.29.0 strict scan:119 selected Python files,6 rules,0 findings,
  **0 reported analysis errors**. All44 API production Python files were included,
  including control_definitions.py. This is not exhaustive OWASP coverage.
- Five gate regressions and real positive/negative rule fixtures PASS.
- API Ruff format/check and strict mypy:82 files PASS.
- API unit tests99 PASS;573 DB tests skipped outside their harness are not passes.
- Existing process integrity suite202 PASS in a new loopback-only disposable
  fixture. Private harness reused the existing test image and used512MB tmpfs;
  source test cases/DB guards were unchanged. No real demo/customer DB writes.
  An initial invocation without the local-tools wrapper lacked Docker and failed
  before creating a container; corrected invocation passed without installing
  dependencies. The runs are retained separately and not counted twice.
- Standalone before/after OpenAPI probe prohibited network connections and
  produced byte-identical4-path schema SHA256
  `846b55136402d25d52e04eae43db1b8304712966c3f12d2ad84dbf533b2aea8c`.
- ShellCheck, Bash syntax and diff checks PASS. Independent bounded review found
  no new P0/P1/P2 issues; reviewer did not re-run DB suites or inspect secrets.

The official native1.29.0 asset was verified against release SHA256
`dacc12a24e95b22c8b1ab55be1777b6eb877a922c5571a95b9a8de30f3963438`.
Linux CI asset/version/checksum remain unchanged. No signature verification or
new runtime dependency is claimed. OpenGrep2.0 evaluation remains unintegrated.

## Recovery and disposition

CP-SAST-GATE-00-20261117T152512Z protects702 source/Git files atffb2dded before
changes. External AES-256-GCM decryption, isolated all-file SHA256/mode restore,
Git bundle verification and tamper rejection PASS. No database schema migration
or real DB restore is part of this change.

Exact-head CI is required after publication. The six known HIGH findings in the
latest official Keycloak26.8.2 remain a separate release blocker. No source of
truth, license, tenant boundary, approval policy, API or production deployment is
changed; no original PR has been merged/closed to hide the blocker.
