#!/usr/bin/env bash
set -euo pipefail

env_file=${1:?Usage: collect-release-image-evidence.sh ENV_FILE SOURCE_SHA RUN_ID}
source_sha=${2:?Missing source SHA}
run_id=${3:?Missing workflow run ID}
output=artifacts/release-image-evidence.json
mkdir -p artifacts
# Do not permit an accidentally overlapping input/output path.
python3 - "$env_file" "$output" <<'PY'
import sys
from pathlib import Path
if Path(sys.argv[1]).resolve() == Path(sys.argv[2]).resolve():
    raise SystemExit('environment file must not overlap release evidence')
PY
rm -f "$output"

# The full rendered Compose configuration may contain credentials. Keep it in
# the pipe; write only validated public image references to the evidence folder.
docker compose --env-file "$env_file" config --format json |
  python3 -c 'import json,sys; sys.path.insert(0,"scripts"); from release_image_evidence import compose_vendor_references; json.dump(compose_vendor_references(json.load(sys.stdin)),sys.stdout)' \
  > artifacts/vendor-image-references.json
vendor_line=$(python3 -c 'import json; r=json.load(open("artifacts/vendor-image-references.json")); print(" ".join(r[n] for n in ("seaweedfs","keycloak","clamav")))')
read -r seaweedfs_image keycloak_image clamav_image <<< "$vendor_line"

docker image inspect "pmcloud-api:${source_sha}" "pmcloud-web:${source_sha}" pmcloud-postgres:local \
  "$seaweedfs_image" "$keycloak_image" "$clamav_image" |
  python3 -c 'import json,sys; keys=("Id","Os","Architecture","RepoTags","RepoDigests"); json.dump([{k:r.get(k) for k in keys} for r in json.load(sys.stdin)],sys.stdout)' \
  > artifacts/scanned-images.json
python3 scripts/release_image_evidence.py \
  --inspection artifacts/scanned-images.json \
  --scan-started-at artifacts/image-scan-started-at.txt \
  --source-sha "$source_sha" --run-id "$run_id" \
  --report api "pmcloud-api:${source_sha}" artifacts/trivy-api-image.json \
  --report web "pmcloud-web:${source_sha}" artifacts/trivy-web-image.json \
  --report postgres pmcloud-postgres:local artifacts/trivy-postgres-image.json \
  --report seaweedfs "$seaweedfs_image" artifacts/trivy-seaweedfs-image.json \
  --report keycloak "$keycloak_image" artifacts/trivy-keycloak-image.json \
  --report clamav "$clamav_image" artifacts/trivy-clamav-image.json \
  --output "$output"
