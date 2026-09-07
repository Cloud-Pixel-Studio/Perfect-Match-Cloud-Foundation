#!/usr/bin/env bash
set -euo pipefail

container="pmcloud-tenant-isolation-$$"
port=${PMC_TEST_POSTGRES_PORT:-55432}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --detach --rm \
  --name "$container" \
  --publish "127.0.0.1:${port}:5432" \
  --env POSTGRES_DB=pmcloud_isolation \
  --env POSTGRES_USER=pmcloud_bootstrap \
  --env POSTGRES_PASSWORD="$bootstrap_password" \
  postgres:18-alpine@sha256:24b9bbcd16361b62a3051ed06287050fd9a61f6fb6d36f1850eae4b741c61ce3 >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_isolation >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_isolation >/dev/null

export POSTGRES_DB=pmcloud_isolation
export POSTGRES_MIGRATION_USER=pmcloud_migrator
export POSTGRES_MIGRATION_PASSWORD="$migration_password"
export POSTGRES_RUNTIME_USER=pmcloud_app
export POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_isolation"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_isolation"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL"
export PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_isolation"
login_transaction_key=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')
export PMC_LOGIN_TRANSACTION_KEY="$login_transaction_key"

(
  cd apps/api
  ready=false
  for _ in $(seq 1 20); do
    if uv run --no-sync python -m pmc_api.bootstrap_database >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ "$ready" != true ]]; then
    uv run --no-sync python -m pmc_api.bootstrap_database
    exit 1
  fi
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest -m tenant_isolation
)
