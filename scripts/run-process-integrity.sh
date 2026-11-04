#!/usr/bin/env bash
set -euo pipefail

./scripts/build-test-postgres.sh

container="pmcloud-process-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55436}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
downgrade_log=$(mktemp "${TMPDIR:-/tmp}/pmcloud-downgrade.XXXXXX")
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  test ! -e "$downgrade_log" || unlink "$downgrade_log"
}
trap cleanup EXIT

docker run --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" \
  --env POSTGRES_DB=pmcloud_process --env POSTGRES_USER=pmcloud_bootstrap \
  --env POSTGRES_PASSWORD="$bootstrap_password" \
  pmcloud-postgres:local >/dev/null
for _ in $(seq 1 30); do
  docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_process >/dev/null 2>&1 && break
  sleep 1
done
export POSTGRES_DB=pmcloud_process POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password"
export POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_process"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_process"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL"
export PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_process"
login_transaction_key="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
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
  uv run --no-sync alembic downgrade 0008_qms_capabilities
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest -m process_integrity tests/test_process_integrity.py tests/test_risk_integrity.py tests/test_risk_link_integrity.py tests/test_nonconformity_integrity.py tests/test_ncr_link_integrity.py tests/test_ncr_evidence_link_integrity.py tests/test_capa_intake_integrity.py tests/test_capa_document_link_integrity.py tests/test_capa_trace_link_integrity.py
  if uv run --no-sync alembic downgrade 0008_qms_capabilities >"$downgrade_log" 2>&1; then
    echo "Process audit downgrade unexpectedly succeeded" >&2
    exit 1
  fi
  if ! grep -q "cannot discard CAPA trace link history" "$downgrade_log"; then
    echo "Process audit downgrade failed for an unexpected reason" >&2
    sed -n '1,120p' "$downgrade_log" >&2
    exit 1
  fi
  echo "Protected CAPA history blocked destructive downgrade: PASS"
)
