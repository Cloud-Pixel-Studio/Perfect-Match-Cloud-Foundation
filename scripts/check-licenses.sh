#!/usr/bin/env bash
set -euo pipefail

mkdir -p artifacts/licenses

if ! (
  cd apps/api
  uv run pip-licenses --format=json --output-file=../../artifacts/licenses/python.json
); then
  printf 'Python license inventory generation failed.\n' >&2
  exit 1
fi

if ! pnpm licenses list --json > artifacts/licenses/node.json; then
  printf 'Node license inventory generation failed.\n' >&2
  exit 1
fi

python3 scripts/validate-licenses.py \
  artifacts/licenses/python.json \
  artifacts/licenses/node.json \
  --summary-file artifacts/licenses/summary.json
