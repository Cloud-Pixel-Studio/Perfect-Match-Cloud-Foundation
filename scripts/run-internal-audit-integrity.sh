#!/usr/bin/env bash
set -euo pipefail

./scripts/build-test-postgres.sh

container="pmcloud-internal-audit-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55439}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
downgrade_log=$(mktemp "${TMPDIR:-/tmp}/pmcloud-internal-audit-downgrade.XXXXXX")
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  test ! -e "$downgrade_log" || unlink "$downgrade_log"
}
trap cleanup EXIT

docker run --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" \
  --env POSTGRES_DB=pmcloud_internal_audit --env POSTGRES_USER=pmcloud_bootstrap \
  --env POSTGRES_PASSWORD="$bootstrap_password" \
  pmcloud-postgres:local >/dev/null
for _ in $(seq 1 30); do
  docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_internal_audit >/dev/null 2>&1 && break
  sleep 1
done
export POSTGRES_DB=pmcloud_internal_audit POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password"
export POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_internal_audit"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_internal_audit"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL"
export PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_internal_audit"
login_transaction_key=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')
export PMC_LOGIN_TRANSACTION_KEY="$login_transaction_key"

(
  cd apps/api
  ready=false
  for _ in $(seq 1 20); do
    if uv run --no-sync python -m pmc_api.bootstrap_database >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
  done
  test "$ready" = true
  uv run --no-sync alembic upgrade head
  uv run --no-sync alembic downgrade 0039_capa_trace_links
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest -m internal_audit_integrity tests/test_internal_audit_integrity.py tests/test_internal_audit_scope_integrity.py tests/test_internal_audit_criteria_integrity.py tests/test_internal_audit_team_integrity.py tests/test_internal_audit_agenda_integrity.py tests/test_internal_audit_independence_integrity.py
  if uv run --no-sync alembic downgrade 0039_capa_trace_links >"$downgrade_log" 2>&1; then
    echo "Internal-audit operational history downgrade unexpectedly succeeded" >&2
    exit 1
  fi
  if ! grep -q "cannot discard internal audit operational history" "$downgrade_log"; then
    echo "Internal-audit downgrade failed for an unexpected reason" >&2
    sed -n '1,120p' "$downgrade_log" >&2
    exit 1
  fi
  echo "Protected internal-audit history blocked destructive downgrade: PASS"
)
