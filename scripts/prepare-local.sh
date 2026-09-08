#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
runtime_dir=$(dirname "$env_file")
mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

if [[ ! -f "$env_file" ]]; then
  umask 077
  postgres_password=$(openssl rand -hex 24)
  postgres_migration_password=$(openssl rand -hex 24)
  postgres_runtime_password=$(openssl rand -hex 24)
  storage_access=$(openssl rand -hex 12)
  storage_secret=$(openssl rand -hex 32)
  storage_signing=$(openssl rand -base64 48 | tr -d '\n')
  {
    printf 'POSTGRES_DB=pmcloud_dev\n'
    printf 'POSTGRES_USER=pmcloud_dev\n'
    printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password"
    printf 'POSTGRES_MIGRATION_USER=pmcloud_migrator\n'
    printf 'POSTGRES_MIGRATION_PASSWORD=%s\n' "$postgres_migration_password"
    printf 'POSTGRES_RUNTIME_USER=pmcloud_app\n'
    printf 'POSTGRES_RUNTIME_PASSWORD=%s\n' "$postgres_runtime_password"
    printf 'SEAWEEDFS_ACCESS_KEY=%s\n' "$storage_access"
    printf 'SEAWEEDFS_SECRET_KEY=%s\n' "$storage_secret"
    printf 'SEAWEEDFS_SIGNING_KEY=%s\n' "$storage_signing"
    printf 'PMC_RUNTIME_DIR=%s\n' "$runtime_dir"
    printf 'APP_VERSION=0.4.0\n'
    printf 'WEB_BUILD_TARGET=runtime\n'
  } > "$env_file"
fi

ensure_secret() {
  local name=$1
  local value=$2
  if ! grep -q "^${name}=" "$env_file"; then
    printf '%s=%s\n' "$name" "$value" >> "$env_file"
  fi
}

ensure_value() {
  local name=$1
  local value=$2
  if ! grep -q "^${name}=" "$env_file"; then
    printf '%s=%s\n' "$name" "$value" >> "$env_file"
  fi
}

ensure_secret POSTGRES_MIGRATION_PASSWORD "$(openssl rand -hex 24)"
ensure_secret POSTGRES_RUNTIME_PASSWORD "$(openssl rand -hex 24)"
ensure_secret KEYCLOAK_ADMIN_PASSWORD "$(openssl rand -hex 24)"
ensure_secret KEYCLOAK_USER_A_PASSWORD "$(openssl rand -hex 24)"
ensure_secret KEYCLOAK_USER_B_PASSWORD "$(openssl rand -hex 24)"
ensure_secret KEYCLOAK_MULTI_USER_PASSWORD "$(openssl rand -hex 24)"
ensure_secret PMC_LOGIN_TRANSACTION_KEY "$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
ensure_value POSTGRES_MIGRATION_USER pmcloud_migrator
ensure_value POSTGRES_RUNTIME_USER pmcloud_app
ensure_value KEYCLOAK_ADMIN pmcloud-bootstrap-admin
ensure_value OIDC_CLIENT_ID perfect-match-web
ensure_value OIDC_ISSUER http://127.0.0.1:8080/realms/perfect-match
ensure_value OIDC_DISCOVERY_URL http://keycloak:8080/realms/perfect-match/.well-known/openid-configuration
ensure_value OIDC_BACKCHANNEL_BASE_URL http://keycloak:8080
ensure_value OIDC_CALLBACK_URL http://127.0.0.1:8000/auth/callback
ensure_value PMC_ENVIRONMENT development
ensure_value PMC_COOKIE_SECURE false
ensure_value PMC_WEB_URL http://127.0.0.1:3000

if grep -q '^APP_VERSION=' "$env_file"; then
  sed -i 's/^APP_VERSION=.*/APP_VERSION=0.4.0/' "$env_file"
else
  printf 'APP_VERSION=0.4.0\n' >> "$env_file"
fi

chmod 600 "$env_file"
set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

export SEAWEEDFS_ACCESS_KEY SEAWEEDFS_SECRET_KEY
python3 - "$runtime_dir/seaweedfs-s3.json" <<'PY'
import json
import os
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
config = {
    "identities": [
        {
            "name": "pmcloud-local",
            "credentials": [
                {
                    "accessKey": os.environ["SEAWEEDFS_ACCESS_KEY"],
                    "secretKey": os.environ["SEAWEEDFS_SECRET_KEY"],
                }
            ],
            "actions": ["Admin", "Read", "List", "Tagging", "Write"],
        }
    ]
}
target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
target.chmod(0o600)
PY

printf 'Local runtime configuration ready at %s\n' "$runtime_dir"
