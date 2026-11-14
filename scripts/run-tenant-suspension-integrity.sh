#!/usr/bin/env bash
set -euo pipefail

./scripts/build-test-postgres.sh
container="pmcloud-tenant-suspension-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55464}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --tmpfs /var/lib/postgresql:rw,nosuid,nodev,size=512m --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" --env POSTGRES_DB=pmcloud_tenant_suspension --env POSTGRES_USER=pmcloud_bootstrap --env POSTGRES_PASSWORD="$bootstrap_password" pmcloud-postgres:local >/dev/null
for _ in $(seq 1 30); do docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_tenant_suspension >/dev/null 2>&1 && break; sleep 1; done
export POSTGRES_DB=pmcloud_tenant_suspension POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password" POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL" PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
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
  uv run --no-sync alembic upgrade "${PMC_TEST_SCHEMA_REVISION:-head}"
  if [ "${PMC_TEST_SCHEMA_REVISION:-head}" = head ]; then
    uv run --no-sync alembic downgrade 0048_audit_competence
    uv run --no-sync alembic upgrade head
  fi
  uv run --no-sync pytest -m tenant_suspension_integrity tests/test_tenant_suspension_integrity.py "$@"
)
