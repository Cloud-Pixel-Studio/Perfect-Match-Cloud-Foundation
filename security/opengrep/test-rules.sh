#!/usr/bin/env bash
set -euo pipefail

rules=security/opengrep/rules.yml
positive=security/tests/fixtures/wildcard_cors_positive.py
negative=security/tests/fixtures/wildcard_cors_negative.py

if opengrep scan --quiet --error --config "$rules" "$positive" >/dev/null 2>&1; then
  printf 'Positive fixture did not trigger.\n' >&2
  exit 1
fi

opengrep scan --quiet --error --config "$rules" "$negative" >/dev/null
printf 'Custom OpenGrep rule fixtures passed.\n'
