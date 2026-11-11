#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
update=${2:-false}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
playwright_image="mcr.microsoft.com/playwright:v1.64.1-noble@sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f"

# shellcheck disable=SC1090
source "$env_file"
export KEYCLOAK_USER_A_PASSWORD
export KEYCLOAK_OWNER_PASSWORD

playwright_command="./node_modules/.bin/playwright test"
if [[ "$update" == "true" ]]; then
  playwright_command+=" --update-snapshots"
fi

if ! docker image inspect "$playwright_image" >/dev/null 2>&1; then
  docker pull "$playwright_image"
fi

docker run --rm \
  --network host \
  --env CI="${CI:-true}" \
  --env KEYCLOAK_USER_A_PASSWORD \
  --env KEYCLOAK_OWNER_PASSWORD \
  --env PLAYWRIGHT_API_URL="http://127.0.0.1:8000" \
  --env PLAYWRIGHT_BASE_URL="http://127.0.0.1:3000" \
  --mount "type=bind,source=${repo_root},target=/work" \
  --workdir /work/apps/web \
  "$playwright_image" \
  bash -lc "$playwright_command"
