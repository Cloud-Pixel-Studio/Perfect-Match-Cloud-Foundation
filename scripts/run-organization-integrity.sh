#!/usr/bin/env bash
set -euo pipefail

container="pmcloud-organization-integrity-$$"
port=${PMC_TEST_POSTGRES_PORT:-55433}
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" --env POSTGRES_DB=pmcloud_organization --env POSTGRES_USER=pmcloud_bootstrap --env POSTGRES_PASSWORD="$bootstrap_password" postgres:18-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2 >/dev/null
for _ in $(seq 1 30); do docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_organization >/dev/null 2>&1 && break; sleep 1; done
export POSTGRES_DB=pmcloud_organization POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password" POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_organization"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_organization"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL" PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_organization"
PMC_LOGIN_TRANSACTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
export PMC_LOGIN_TRANSACTION_KEY
(cd apps/api && uv run --no-sync python -m pmc_api.bootstrap_database && uv run --no-sync alembic upgrade head && uv run --no-sync pytest -m organization_integrity tests/test_organization_integrity.py)
