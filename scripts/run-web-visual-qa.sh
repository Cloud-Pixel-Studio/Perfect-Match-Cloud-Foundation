#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
update=${2:-false}

# shellcheck disable=SC1090
source "$env_file"
export KEYCLOAK_USER_A_PASSWORD
export PLAYWRIGHT_API_URL="http://127.0.0.1:8000"
export PLAYWRIGHT_BASE_URL="http://127.0.0.1:3000"

args=(--filter @perfect-match/web test:e2e)
if [[ "$update" == "true" ]]; then
  args=(--filter @perfect-match/web test:e2e:update)
fi

pnpm "${args[@]}"
