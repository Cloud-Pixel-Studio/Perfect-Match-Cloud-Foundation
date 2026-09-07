#!/usr/bin/env bash
set -euo pipefail

# The tenant-isolation harness provisions disposable PostgreSQL, applies all migrations,
# and runs the forced-RLS matrix. Audit service tests then validate server-side payload rules.
./scripts/run-tenant-isolation.sh
(cd apps/api && uv run --no-sync pytest tests/test_audit_service.py)
