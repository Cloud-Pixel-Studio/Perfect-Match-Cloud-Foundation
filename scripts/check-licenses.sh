#!/usr/bin/env bash
set -euo pipefail

mkdir -p artifacts/licenses
(
  cd apps/api
  uv run pip-licenses --format=json --output-file=../../artifacts/licenses/python.json
)
pnpm licenses list --json > artifacts/licenses/node.json

if rg -i 'AGPL|Affero|SSPL|Server Side Public License|UNKNOWN' artifacts/licenses; then
  printf 'Blocked or unknown dependency license detected.\n' >&2
  exit 1
fi

printf 'Dependency license policy check passed.\n'
