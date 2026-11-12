#!/usr/bin/env bash
set -euo pipefail

# Tests and development use the same hardened image. Rebuild against current
# Alpine package metadata; scans still determine whether release is allowed.
docker build --tag pmcloud-postgres:local --file infrastructure/local/postgres.Dockerfile .
