# Supporting records for saved QMS project steps

Status: backend implemented and independently reviewed; frontend and final delivery validation in progress. This report will be completed against the final tested source. No active demo schema change is attributed to the rehearsal below.

A saved project could keep scope, responsibilities, dates and follow-up but could not cite the records supporting an individual step. This delivery adds two typed references: a specific released, clean document revision, and accepted evidence from an active control implementation. Each reference retains the source identity, selected versions, citation rationale and actor. Removing it requires a reason and preserves the original record. A newer source revision does not silently replace the cited revision.

Reading a reference requires `projects.read` and the corresponding `documents.read` or `control_instances.read` in the same active company and unit. Writing additionally requires `projects.manage`. A company owner, project coordinator or assignee receives no implicit operational authority. Referencing an accepted source record does not verify a project step; product gaps retain `feature_pending`.

Migration0051 adds `qms_project_document_links` and `qms_project_evidence_links`, forced RLS, composite scope constraints, active-reference uniqueness and one-way retirement guards. Its trigger locks the project before the step and advances both versions once through the unchanged0050 protocol. Existing status, notes, assignment and dates remain unchanged. The API writes a typed audit event in the same transaction; event narratives are represented by hashes rather than copied text. This does not establish a mandatory audit receipt for arbitrary SQL access.

Candidate selection checks eligibility before pagination and returns project scope and version metadata from the same statement snapshot, including empty and off-end pages. It avoids the older revision/evidence list ceilings. Source eligibility is observed at that statement; later lifecycle changes produce diagnostic states such as changed, superseded, obsolete or archived. They do not rewrite the snapshot. Accepted evidence's underlying attachment is not reassessed merely because it is cited.

The binding interfaces are [QMS_PROJECT_REFERENCE_API_CONTRACT.json](QMS_PROJECT_REFERENCE_API_CONTRACT.json). The design and implementation plan are in `docs/superpowers/specs/2026-11-19-qms-project-evidence-design.md` and the matching plans directory. No dependency, source lifecycle endpoint, grant bootstrap or0050 implementation was changed.

## Verified backend evidence

Source2f0105afbb171b166c0d79efbb26834791d54caf:

- 170 disposable PostgreSQL HTTP/direct-SQL cases passed:93 existing project cases and77 new reference cases. They cover scope/permissions, immutable server-derived snapshots, lifecycle observations, duplicates, rollback, concurrent writes/archive, candidate pagination, Unicode validation and downgrade history guards.
- 144 API unit cases passed;743 skipped database cases are not passes. Ruff/format139 files, mypy88 files, ShellCheck/bash-n and staged Gitleaks passed. Strict SAST:6 rules over2 new Python sources,0 findings/errors. Two preexisting upstream TestClient/AnyIO deprecation warnings remain recorded.
- Empty0050→0051→0050→0051 round trip passed. Reference/audit history prevented downgrade. Fixture checkpoints CP-QMS-PROJECT-REFERENCES-DB-00-20261120T040138Z and CP-QMS-PROJECT-REFERENCES-DB-06-20261120T040835Z restored61/63 table content hashes and rejected ciphertext tampering. Fixture restore evidence excludes owner/ACL/S3/IdP recovery.
- Independent task reviewer found no P0/P1/P2 in the bounded API/SQL scope and approved both specification compliance and task quality. It checked the unchanged0050 protocol and recorded evidence limits. This is not human approval to merge.
- CP-QMS-PROJECT-REFERENCES-API-01-20261120T044504Z restored778 source files/Git with hashes/modes/bundle verification and authenticated encryption. Keys and actual backups remain outside Git.

Two existing test assumptions were adjusted with explicit controller ownership: capture the pre-downgrade revision rather than hardcode0050 at the new head, and satisfy monotonic timestamp preconditions before testing direct-SQL note content. The earlier intermittent timestamp guard failure and the host/container clock hypothesis remain recorded; no measured clock delta or application fix is claimed. Intermediate fixture mistakes are not presented as feature RED results.

## Demo preparation evidence

The user authorized the synthetic demo update after validation. Initial inventory still found API account-switch-20261117, webd707210 and schema0049/57 tables. Public marketing and protected panel routes were confirmed. A real HTTPS/OIDC connected-study verification passed before the update, including eight private PDF downloads with expected hashes.

CP-QMS-DEMO-BASELINE-VERIFIED-20261120T052809Z restored the current57-table demo database in a no-network clone with role flags/membership, ownership, ACL, RLS and sequence checks. Six encrypted artifacts were copied off the VM and decrypted/hash-verified with a separate key. The restoration excludes role password reapplication, S3 and IdP volumes. The effective ACL comparison follows PostgreSQL defaults; policy SQL is reparsed only in a rolled-back clone transaction after checking policy identities/roles/commands, with a role-widening negative control.

CP-QMS-DEMO-MIGRATION-REHEARSAL-20261120T075722Z additionally migrated that isolated clone using the reviewed amd64 API image and the real migration role.0049/57 tables advanced to0051/63; all previous table content except Alembic revision was preserved. The active database did not migrate. The exported API image archive passed the configured high/critical vulnerability gate. A local emulated web dependency build failed with Tokio BadFD; the native VM dependency build passed without changing pnpm, the lockfile or Dockerfile.

Final frontend/browser/CI results, installed source/images, study examples and rollback disposition remain pending. See [demo rollout](../demo/PROJECTS_ROLLOUT_2026-11-19.md). Production remains subject to the existing release gates; no gate waiver or provider substitution is part of this delivery.

Actualización22noviembre: el frontend parcial quedó preservado al agotarse la cuota del implementador. El controlador corrigió los errores observados de lint y tipado del test.360 pruebas unitarias web, lint, typecheck y build pasaron localmente. Estos resultados no sustituyen la revisión independiente ni la ejecución de las pruebas de navegador nuevas. El navegador local fue rechazado por la configuración Work; no se ejecutó una alternativa que evadiera esa restricción. La inspecciónSSH confirmó que AWS aún mantiene APIaccount-switch-20261117/webd707210/esquema0049. No se instaló la entrega.
