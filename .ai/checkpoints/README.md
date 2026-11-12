# Recovery checkpoint contract

Checkpoints are evidence manifests plus encrypted recovery artifacts outside the
working tree. A Git commit is not a backup.

Required series:

- CP-00 initial local baseline.
- CP-01 verified architecture and risk audit.
- CP-02 last recoverable state before agent configuration.
- CP-03 agent configuration plus tests.
- CP-04 security hardening plus residual findings.
- CP-05 UI/UX baseline plus masked screenshots.
- CP-06 final pre-PR verification.

Every checkpoint records UTC identifier, repository path, branch, commit, dirty
inventory, dependency locks, schema version, verification results, artifact hashes
and recovery status. Source, Git history and database backups are encrypted outside
the repository. Keys are stored separately with least privilege. Customer data,
environment files and production secrets are never copied into the repository.

Database checkpoints require a custom-format logical dump and an isolated restore
test. A manifest may say `captured` only after encryption and checksums; it may say
`recovery verified` only after archive listing, Git-bundle verification and database
restore have succeeded.
