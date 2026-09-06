#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
make lint ENV_FILE="$env_file"
make typecheck ENV_FILE="$env_file"
make test ENV_FILE="$env_file"
make build ENV_FILE="$env_file"
make health ENV_FILE="$env_file"
./security/opengrep/test-rules.sh
opengrep scan --config security/opengrep/rules.yml --exclude security/tests/fixtures .
gitleaks dir --config .gitleaks.toml --redact --no-banner .
gitleaks git --config .gitleaks.toml --redact --no-banner .
./scripts/check-licenses.sh

printf 'Focused checkpoint commands passed. Full scanner evidence is collected separately.\n'
