#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
make lint ENV_FILE="$env_file"
make typecheck ENV_FILE="$env_file"
make test ENV_FILE="$env_file"
./scripts/run-audit-integrity.sh
./scripts/run-organization-integrity.sh
./scripts/run-workflow-integrity.sh
./scripts/run-qms-access-integrity.sh
./scripts/run-qms-access-history-integrity.sh
./scripts/run-tenant-suspension-integrity.sh
./scripts/run-internal-audit-integrity.sh
./scripts/run-process-integrity.sh
make build ENV_FILE="$env_file"
make health ENV_FILE="$env_file"
./security/opengrep/test-rules.sh
opengrep scan --no-git-ignore --config security/opengrep/rules.yml --exclude security/tests/fixtures .
gitleaks dir --config .gitleaks.toml --redact --no-banner .
gitleaks git --config .gitleaks.toml --redact --no-banner .
python3 security/tests/test_checkpoint_secret_allowlist.py
./scripts/check-licenses.sh

printf 'Focused checkpoint commands passed. Full scanner evidence is collected separately.\n'
