#!/usr/bin/env bash
set -euo pipefail

container="pmcloud-workflow-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55434}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" \
  --env POSTGRES_DB=pmcloud_workflow --env POSTGRES_USER=pmcloud_bootstrap \
  --env POSTGRES_PASSWORD="$bootstrap_password" \
  postgres:18-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2 >/dev/null
for _ in $(seq 1 30); do
  docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_workflow >/dev/null 2>&1 && break
  sleep 1
done
export POSTGRES_DB=pmcloud_workflow POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password"
export POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_workflow"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_workflow"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL"
export PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_workflow"
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
  uv run --no-sync pytest -m workflow_integrity tests/test_workflow_integrity.py
)
