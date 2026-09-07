#!/usr/bin/env bash
set -euo pipefail

rules=security/opengrep/rules.yml
for positive in security/tests/fixtures/*_positive.py; do
  if opengrep scan --quiet --error --config "$rules" "$positive" >/dev/null 2>&1; then
    printf 'Positive fixture did not trigger: %s\n' "$positive" >&2
    exit 1
  fi
done

for negative in security/tests/fixtures/*_negative.py; do
  opengrep scan --quiet --error --config "$rules" "$negative" >/dev/null
done
printf 'Custom OpenGrep rule fixtures passed.\n'
