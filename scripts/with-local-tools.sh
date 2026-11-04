#!/usr/bin/env bash
set -euo pipefail

# Optional workspace-local toolchain. No shell-profile or system Node changes.
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
container_tools="${project_root}/artifacts/tooling/containers"
export PATH="${container_tools}/bin:${project_root}/artifacts/tooling/node_modules/.bin:${project_root}/artifacts/tooling/python/bin:${PATH}"
if [ -z "${DOCKER_CONFIG:-}" ] && [ -f "${container_tools}/docker-config/config.json" ]; then
  export DOCKER_CONFIG="${container_tools}/docker-config"
fi
if [ -z "${DOCKER_HOST:-}" ] && [ -z "${DOCKER_CONTEXT:-}" ] && [ -S "${HOME}/.colima/pmqms/docker.sock" ]; then
  export DOCKER_HOST="unix://${HOME}/.colima/pmqms/docker.sock"
fi

if [ "$#" -eq 0 ]; then
  echo 'Usage: ./scripts/with-local-tools.sh <command> [arguments...]' >&2
  exit 2
fi

exec "$@"
