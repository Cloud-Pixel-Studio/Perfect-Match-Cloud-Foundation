#!/usr/bin/env bash
set -euo pipefail

if [ "${PMC_TEST_REUSE_POSTGRES_IMAGE:-0}" = 1 ]; then
  docker image inspect pmcloud-postgres:local >/dev/null
else
  ./scripts/build-test-postgres.sh
fi
container="pmcloud-qms-project-reference-integrity-$$"
restore_container="${container}-restore"
port=${PMC_TEST_POSTGRES_PORT:-}
if [[ -n "$port" ]] && { [[ ! "$port" =~ ^[0-9]+$ ]] || (( 10#$port < 1 || 10#$port > 65535 )); }; then
  echo "PMC_TEST_POSTGRES_PORT must be a TCP port between 1 and 65535" >&2
  exit 2
fi
bootstrap_password=$(openssl rand -hex 24)
migration_password=$(openssl rand -hex 24)
runtime_password=$(openssl rand -hex 24)
downgrade_log=$(mktemp "${TMPDIR:-/tmp}/pmcloud-project-downgrade.XXXXXX")
cleanup() {
  docker rm -f "$container" "$restore_container" >/dev/null 2>&1 || true
  test ! -e "$downgrade_log" || unlink "$downgrade_log"
}
trap cleanup EXIT
docker run --tmpfs /var/lib/postgresql:rw,nosuid,nodev,size=512m --detach --rm --name "$container" --publish "127.0.0.1:${port}:5432" --env POSTGRES_DB=pmcloud_tenant_suspension --env POSTGRES_USER=pmcloud_bootstrap --env POSTGRES_PASSWORD="$bootstrap_password" pmcloud-postgres:local >/dev/null
binding=$(docker port "$container" 5432/tcp)
if [[ ! "$binding" =~ ^127\.0\.0\.1:([0-9]+)$ ]]; then
  echo "Unable to resolve isolated PostgreSQL loopback binding" >&2
  exit 1
fi
port=${BASH_REMATCH[1]}
for _ in $(seq 1 30); do docker exec "$container" pg_isready -U pmcloud_bootstrap -d pmcloud_tenant_suspension >/dev/null 2>&1 && break; sleep 1; done
export POSTGRES_DB=pmcloud_tenant_suspension POSTGRES_MIGRATION_USER=pmcloud_migrator POSTGRES_MIGRATION_PASSWORD="$migration_password" POSTGRES_RUNTIME_USER=pmcloud_app POSTGRES_RUNTIME_PASSWORD="$runtime_password"
export PMC_DATABASE_ADMIN_URL="postgresql+pg8000://pmcloud_bootstrap:${bootstrap_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
export PMC_DATABASE_URL="postgresql+pg8000://pmcloud_migrator:${migration_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
export PMC_TEST_ADMIN_DATABASE_URL="$PMC_DATABASE_ADMIN_URL" PMC_TEST_RUNTIME_DATABASE_URL="postgresql+pg8000://pmcloud_app:${runtime_password}@127.0.0.1:${port}/pmcloud_tenant_suspension"
PMC_LOGIN_TRANSACTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
export PMC_LOGIN_TRANSACTION_KEY
export PMC_PROJECT_TEST_CONTAINER="$container" PMC_PROJECT_RESTORE_CONTAINER="$restore_container"
for attempt in $(seq 1 20); do
  if (cd apps/api && uv run --no-sync python -m pmc_api.bootstrap_database >/dev/null 2>&1); then break; fi
  if [ "$attempt" = 20 ]; then echo "Disposable DB bootstrap failed" >&2; exit 1; fi
  sleep 1
done

snapshot() {
  PMC_PROJECT_SNAPSHOT_PHASE="$1" apps/api/.venv/bin/python - <<'PY'
import hashlib
import json
import os
import secrets
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

source, restored = os.environ['PMC_PROJECT_TEST_CONTAINER'], os.environ['PMC_PROJECT_RESTORE_CONTAINER']
phase = os.environ['PMC_PROJECT_SNAPSHOT_PHASE']
label = f'CP-QMS-PROJECT-REFERENCES-DB-{phase}-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
archive = Path.home() / 'Library/Application Support/PerfectMatchQMS/checkpoints' / label
keys = Path.home() / '.config/pmcloud/checkpoint-keys'
archive.mkdir(parents=True, mode=0o700)
keys.mkdir(parents=True, exist_ok=True, mode=0o700)
def run(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout
def sql(container, query):
    return run(['docker', 'exec', '-i', container, 'psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-U', 'pmcloud_bootstrap', '-d', 'pmcloud_tenant_suspension'], input=query.encode())
def manifest(container):
    tables = sql(container, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").decode().splitlines()
    result = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        rows = sql(container, f"SELECT COALESCE(jsonb_agg(t ORDER BY t::text),'[]'::jsonb)::text FROM (SELECT to_jsonb(x) t FROM public.{quoted} x) z")
        result[table] = {'rows': len(json.loads(rows)), 'sha256': hashlib.sha256(rows).hexdigest()}
    return result
before = manifest(source)
dump = run(['docker', 'exec', source, 'pg_dump', '-Fc', '--no-owner', '--no-acl', '-U', 'pmcloud_bootstrap', '-d', 'pmcloud_tenant_suspension'])
key, nonce = AESGCM.generate_key(bit_length=256), secrets.token_bytes(12)
cipher = nonce + AESGCM(key).encrypt(nonce, dump, label.encode())
(archive / 'database.dump.aesgcm').write_bytes(cipher)
key_path = keys / (label + '.key')
key_path.write_bytes(key)
key_path.chmod(0o600)
plaintext = AESGCM(key_path.read_bytes()).decrypt(cipher[:12], cipher[12:], label.encode())
assert hashlib.sha256(plaintext).digest() == hashlib.sha256(dump).digest()
changed = bytearray(cipher)
changed[-1] ^= 1
try:
    AESGCM(key).decrypt(bytes(changed[:12]), bytes(changed[12:]), label.encode())
    raise AssertionError('tampered archive accepted')
except Exception as error:
    assert type(error).__name__ == 'InvalidTag'
run(['docker', 'run', '--network', 'none', '--tmpfs', '/var/lib/postgresql:rw,nosuid,nodev,size=512m', '--detach', '--rm', '--name', restored, '--env', 'POSTGRES_DB=pmcloud_tenant_suspension', '--env', 'POSTGRES_USER=pmcloud_bootstrap', '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', 'pmcloud-postgres:local'])
try:
    for _ in range(40):
        try:
            sql(restored, 'SELECT 1')
            break
        except subprocess.CalledProcessError:
            time.sleep(.5)
    sql(restored, 'CREATE ROLE pmcloud_migrator; CREATE ROLE pmcloud_app;')
    # Restore database content only: owners/ACL are intentionally not claimed.
    run(['docker', 'exec', '-i', restored, 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '-U', 'pmcloud_bootstrap', '-d', 'pmcloud_tenant_suspension'], input=plaintext)
    assert manifest(restored) == before
finally:
    run(['docker', 'rm', '-f', restored])
(archive / 'manifest.json').write_text(json.dumps({'label': label, 'tables': before, 'restore_data_hashes_equal': True, 'tamper_rejected': True}, indent=2) + '\n')
print(f'{label}: encrypted dump, separate key, isolated tmpfs restore, {len(before)} table hashes and tamper rejection PASS')
PY
}
(
  cd apps/api
  uv run --no-sync alembic upgrade 0050_qms_projects
)
snapshot 00
if [ "${PMC_PROJECT_REFERENCE_RED_ONLY:-0}" = 1 ]; then
  (cd apps/api && uv run --no-sync pytest tests/test_qms_project_reference_integrity.py -x)
  exit 1
fi
(
  cd apps/api
  uv run --no-sync alembic upgrade head
  uv run --no-sync alembic downgrade 0050_qms_projects
  uv run --no-sync alembic upgrade head
  uv run --no-sync pytest "$@" tests/test_qms_project_integrity.py tests/test_qms_project_reference_integrity.py
  if uv run --no-sync alembic downgrade 0050_qms_projects >"$downgrade_log" 2>&1; then
    echo "Project history downgrade unexpectedly succeeded" >&2
    exit 1
  fi
  if ! grep -q 'cannot discard QMS project reference history' "$downgrade_log"; then
    echo "Project downgrade failed for an unexpected reason" >&2
    exit 1
  fi
  echo "Protected reference history blocked destructive downgrade: PASS"
)
snapshot 06
(
  cd apps/api
  uv run --no-sync pytest "$@" tests/test_qms_context_integrity.py \
    tests/test_qms_party_requirements_integrity.py tests/test_qms_party_process_links_integrity.py \
    tests/test_qms_party_document_links_integrity.py tests/test_qms_party_evidence_links_integrity.py \
    tests/test_qms_party_risk_links_integrity.py \
    tests/test_qms_context_upgrade_rehearsal.py
)
