#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
runtime_dir=$(dirname "$env_file")
mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

if [[ ! -f "$env_file" ]]; then
  umask 077
  postgres_password=$(openssl rand -hex 24)
  storage_access=$(openssl rand -hex 12)
  storage_secret=$(openssl rand -hex 32)
  storage_signing=$(openssl rand -base64 48 | tr -d '\n')
  {
    printf 'POSTGRES_DB=pmcloud_dev\n'
    printf 'POSTGRES_USER=pmcloud_dev\n'
    printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password"
    printf 'SEAWEEDFS_ACCESS_KEY=%s\n' "$storage_access"
    printf 'SEAWEEDFS_SECRET_KEY=%s\n' "$storage_secret"
    printf 'SEAWEEDFS_SIGNING_KEY=%s\n' "$storage_signing"
    printf 'PMC_RUNTIME_DIR=%s\n' "$runtime_dir"
    printf 'APP_VERSION=0.1.0\n'
    printf 'WEB_BUILD_TARGET=runtime\n'
  } > "$env_file"
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
