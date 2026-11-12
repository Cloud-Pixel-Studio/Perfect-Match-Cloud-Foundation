#!/usr/bin/env bash
set -Eeuo pipefail

./scripts/build-test-postgres.sh

container="pmcloud-tenant-isolation-$$"
port=${PMC_TEST_POSTGRES_PORT:-}
if [[ -n "$port" ]] && { [[ ! "$port" =~ ^[0-9]+$ ]] || (( 10#$port < 1 || 10#$port > 65535 )); }; then
  echo "PMC_TEST_POSTGRES_PORT must be a TCP port between 1 and 65535" >&2
  exit 2
fi
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
diagnose() {
  local status=$?
  echo "tenant-isolation failed (exit ${status}); container=${container}" >&2
  docker ps -a --filter "name=${container}" --format '{{.Names}} {{.Status}}' >&2 || true
  docker logs --tail 80 "$container" >&2 || true
  exit "$status"
}
trap diagnose ERR
trap cleanup EXIT

docker run --detach --rm \
  --name "$container" \
  --publish "127.0.0.1:${port}:5432" \
  --env POSTGRES_DB=pmcloud_isolation \
  --env POSTGRES_USER=pmcloud_bootstrap \
  --env POSTGRES_PASSWORD="$bootstrap_password" \
  pmcloud-postgres:local >/dev/null

if [[ -z "$port" ]]; then
  binding=$(docker port "$container" 5432/tcp)
  port=${binding##*:}
  if [[ ! "$port" =~ ^[0-9]+$ ]]; then
    echo "Unable to resolve Docker-assigned PostgreSQL port: $binding" >&2
    exit 1
  fi
fi

# The official PostgreSQL entrypoint starts a temporary socket-only server
# during initdb, then shuts it down before starting the final TCP server.
# A socket pg_isready check can succeed during that temporary phase.
ready=false
for _ in $(seq 1 60); do
  if docker exec -e PGPASSWORD="$bootstrap_password" "$container" \
    psql -h 127.0.0.1 -U pmcloud_bootstrap -d pmcloud_isolation \
    -Atqc 'SELECT 1' 2>/dev/null | grep -qx 1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo "PostgreSQL final TCP connection/query did not become ready within 60 seconds" >&2
  exit 1
fi

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
  bootstrap_log=$(mktemp)
  trap 'rm -f "$bootstrap_log"' EXIT
  for attempt in $(seq 1 20); do
    if uv run --no-sync python -m pmc_api.bootstrap_database >"$bootstrap_log" 2>&1; then
      ready=true
      break
    fi
    if [[ "$attempt" -lt 20 ]]; then
      sleep 1
    fi
  done
  if [[ "$ready" != true ]]; then
    echo "Database bootstrap failed after 20 attempts; last output follows:" >&2
    cat "$bootstrap_log" >&2
    exit 1
  fi
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest -m tenant_isolation
)
