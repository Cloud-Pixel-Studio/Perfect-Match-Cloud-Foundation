#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-"${HOME}/.config/pmcloud/dev.env"}
docker compose --env-file "$env_file" ps
for service in database-bootstrap migrate identity-bootstrap; do
  container_id=$(docker compose --env-file "$env_file" ps --all --quiet "$service")
  [[ -n "$container_id" ]]
  [[ $(docker inspect --format '{{.State.ExitCode}}' "$container_id") -eq 0 ]]
done
curl --fail --silent --show-error http://127.0.0.1:8000/health | jq .
curl --fail --silent --show-error http://127.0.0.1:3000/ >/dev/null
curl --fail --silent --show-error \
  http://127.0.0.1:8080/realms/perfect-match/.well-known/openid-configuration \
  | jq --exit-status '.issuer == "http://127.0.0.1:8080/realms/perfect-match"' >/dev/null
printf 'Runtime health checks passed.\n'
