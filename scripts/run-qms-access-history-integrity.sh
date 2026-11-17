#!/usr/bin/env bash
set -euo pipefail

# Reuse an explicitly requested local test image when an isolated audit cannot
# build (for example a full development VM); CI builds the image by default.
if [ "${PMC_TEST_REUSE_POSTGRES_IMAGE:-0}" = 1 ]; then
  docker image inspect pmcloud-postgres:local >/dev/null
else
  ./scripts/build-test-postgres.sh
fi
container="pmcloud-qms-access-history-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55465}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --tmpfs /var/lib/postgresql:rw,nosuid,nodev,size=512m --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" --env POSTGRES_DB=pmcloud_access_history --env POSTGRES_USER=pmcloud_bootstrap --env POSTGRES_PASSWORD="$bootstrap_password" pmcloud-postgres:local >/dev/null
for _ in $(seq 1 30); do docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_access_history >/dev/null 2>&1 && break; sleep 1; done
export POSTGRES_DB=pmcloud_access_history POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password" POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_access_history"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_access_history"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL" PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_access_history"
PMC_LOGIN_TRANSACTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
export PMC_LOGIN_TRANSACTION_KEY
# pg_isready can report ready immediately before PostgreSQL's initialization restart.
for attempt in $(seq 1 20); do
  if (cd apps/api && uv run --no-sync python -m pmc_api.bootstrap_database); then break; fi
  if [ "$attempt" = 20 ]; then exit 1; fi
  sleep 1
done
(
  cd apps/api
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest -m qms_access_history_integrity tests/test_qms_access_history_integrity.py "$@"
)
