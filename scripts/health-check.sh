#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
docker compose --env-file "$env_file" ps
curl --fail --silent --show-error http://127.0.0.1:8000/health | jq .
curl --fail --silent --show-error http://127.0.0.1:3000/ >/dev/null
printf 'Runtime health checks passed.\n'
