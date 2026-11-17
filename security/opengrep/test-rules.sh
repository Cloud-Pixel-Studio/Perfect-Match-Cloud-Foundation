#!/usr/bin/env bash
set -euo pipefail

rules=security/opengrep/rules.yml
scan_log=$(mktemp)
trap 'rm -f "$scan_log"' EXIT
for positive in security/tests/fixtures/*_positive.py; do
  status=0
  opengrep scan --quiet --error --strict --config "$rules" "$positive" >"$scan_log" 2>&1 || status=$?
  if [[ "$status" -ne 1 ]]; then
    printf 'Positive fixture requires finding exit 1, received %s: %s\n' "$status" "$positive" >&2
    cat "$scan_log" >&2
    exit 1
  fi
done

for negative in security/tests/fixtures/*_negative.py; do
  opengrep scan --quiet --error --strict --config "$rules" "$negative" >/dev/null
done
printf 'Custom OpenGrep rule fixtures passed.\n'
