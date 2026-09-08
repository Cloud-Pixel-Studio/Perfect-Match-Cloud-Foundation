#!/usr/bin/env bash
set -euo pipefail

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

write_json() {
  printf '%s\n' "$2" > "$tmp_dir/$1"
}

write_json valid-python.json '[{"Name":"allowed-python","License":"MIT"}]'
write_json valid-node.json '[{"name":"allowed-node","license":"Apache-2.0"}]'
python3 scripts/validate-licenses.py "$tmp_dir/valid-python.json" "$tmp_dir/valid-node.json" --summary-file "$tmp_dir/summary.json" >/dev/null

write_json blocked.json '[{"name":"blocked","license":"AGPL-3.0-only"}]'
if python3 scripts/validate-licenses.py "$tmp_dir/blocked.json" "$tmp_dir/valid-node.json" >/dev/null 2>&1; then
  printf 'blocked license unexpectedly passed.\n' >&2
  exit 1
fi

write_json unknown.json '[{"name":"unknown","license":"UNKNOWN"}]'
if python3 scripts/validate-licenses.py "$tmp_dir/valid-python.json" "$tmp_dir/unknown.json" >/dev/null 2>&1; then
  printf 'unknown license unexpectedly passed.\n' >&2
  exit 1
fi

write_json malformed.json '{not-json}'
if python3 scripts/validate-licenses.py "$tmp_dir/malformed.json" "$tmp_dir/valid-node.json" >/dev/null 2>&1; then
  printf 'malformed inventory unexpectedly passed.\n' >&2
  exit 1
fi

if python3 scripts/validate-licenses.py "$tmp_dir/missing.json" "$tmp_dir/valid-node.json" >/dev/null 2>&1; then
  printf 'missing inventory unexpectedly passed.\n' >&2
  exit 1
fi

printf 'License validator fail-closed regression tests passed.\n'
