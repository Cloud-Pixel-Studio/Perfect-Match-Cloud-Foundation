#!/usr/bin/env bash
set -euo pipefail

readonly OPENGREP_VERSION="1.29.0"
readonly OPENGREP_SHA256="3365ef49d04893e01338d85d9bbd49b2bd5261ad4c9c0df0a6a0f8d44232ae13"
readonly GITLEAKS_VERSION="8.30.1"
readonly GITLEAKS_CHECKSUMS_SHA256="061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae"

readonly OPENGREP_ASSET="opengrep_manylinux_x86"
readonly GITLEAKS_ARCHIVE="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
readonly GITLEAKS_CHECKSUMS="gitleaks_${GITLEAKS_VERSION}_checksums.txt"
readonly OPENGREP_URL="https://github.com/opengrep/opengrep/releases/download/v${OPENGREP_VERSION}/${OPENGREP_ASSET}"
readonly GITLEAKS_RELEASE_URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"

readonly INSTALL_DIR="${HOME}/.local/bin"
readonly DOWNLOAD_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pmc-security-tools"

download() {
  local url="$1"
  local output="$2"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
    --output "$output" "$url"
}

verify_sha256() {
  local expected="$1"
  local file="$2"
  printf '%s  %s\n' "$expected" "$file" | sha256sum --check --strict
}

mkdir -p "$INSTALL_DIR" "$DOWNLOAD_DIR"

opengrep_path="${DOWNLOAD_DIR}/${OPENGREP_ASSET}"
download "$OPENGREP_URL" "$opengrep_path"
verify_sha256 "$OPENGREP_SHA256" "$opengrep_path"
install -m 0755 "$opengrep_path" "${INSTALL_DIR}/opengrep"

gitleaks_archive_path="${DOWNLOAD_DIR}/${GITLEAKS_ARCHIVE}"
gitleaks_checksums_path="${DOWNLOAD_DIR}/${GITLEAKS_CHECKSUMS}"
gitleaks_selected_checksum="${DOWNLOAD_DIR}/gitleaks-selected.sha256"

download "${GITLEAKS_RELEASE_URL}/${GITLEAKS_CHECKSUMS}" "$gitleaks_checksums_path"
download "${GITLEAKS_RELEASE_URL}/${GITLEAKS_ARCHIVE}" "$gitleaks_archive_path"
verify_sha256 "$GITLEAKS_CHECKSUMS_SHA256" "$gitleaks_checksums_path"

if ! grep -F "  ${GITLEAKS_ARCHIVE}" "$gitleaks_checksums_path" > "$gitleaks_selected_checksum"; then
  echo "Gitleaks archive is absent from the verified checksum manifest." >&2
  exit 1
fi

if [[ $(wc -l < "$gitleaks_selected_checksum") -ne 1 ]]; then
  echo "Gitleaks checksum manifest contains an ambiguous archive entry." >&2
  exit 1
fi

(
  cd "$DOWNLOAD_DIR"
  sha256sum --check --strict "$(basename "$gitleaks_selected_checksum")"
)

tar -xzf "$gitleaks_archive_path" -C "$DOWNLOAD_DIR" gitleaks
install -m 0755 "${DOWNLOAD_DIR}/gitleaks" "${INSTALL_DIR}/gitleaks"

if [[ -n "${GITHUB_PATH:-}" ]]; then
  printf '%s\n' "$INSTALL_DIR" >> "$GITHUB_PATH"
fi

[[ $("${INSTALL_DIR}/opengrep" --version) == "$OPENGREP_VERSION" ]]
[[ $("${INSTALL_DIR}/gitleaks" version) == "$GITLEAKS_VERSION" ]]
