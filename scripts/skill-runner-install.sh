#!/usr/bin/env sh
set -e

REPO="${SKILL_RUNNER_RELEASE_REPO:-leike0813/Skill-Runner}"
VERSION=""
INSTALL_ROOT="${SKILL_RUNNER_INSTALL_ROOT:-$HOME/.local/share/skill-runner/releases}"
JSON_OUTPUT=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    --install-root)
      INSTALL_ROOT="$2"
      shift 2
      ;;
    --json)
      JSON_OUTPUT=1
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 2
      ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "--version is required (example: --version v0.4.3)"
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required."
  exit 2
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "tar is required."
  exit 2
fi

ARTIFACT="skill-runner-${VERSION}.tar.gz"
CHECKSUM="${ARTIFACT}.sha256"
BASE_URL="https://github.com/${REPO}/releases/download/${VERSION}"
ARTIFACT_URL="${BASE_URL}/${ARTIFACT}"
CHECKSUM_URL="${BASE_URL}/${CHECKSUM}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ "$JSON_OUTPUT" -eq 1 ]; then
  echo "Downloading ${ARTIFACT_URL}" >&2
else
  echo "Downloading ${ARTIFACT_URL}"
fi
curl -fL "$ARTIFACT_URL" -o "$TMP_DIR/$ARTIFACT"
if [ "$JSON_OUTPUT" -eq 1 ]; then
  echo "Downloading ${CHECKSUM_URL}" >&2
else
  echo "Downloading ${CHECKSUM_URL}"
fi
curl -fL "$CHECKSUM_URL" -o "$TMP_DIR/$CHECKSUM"

if command -v sha256sum >/dev/null 2>&1; then
  if [ "$JSON_OUTPUT" -eq 1 ]; then
    (cd "$TMP_DIR" && sha256sum -c "$CHECKSUM" >/dev/null)
  else
    (cd "$TMP_DIR" && sha256sum -c "$CHECKSUM")
  fi
elif command -v shasum >/dev/null 2>&1; then
  EXPECTED="$(awk '{print $1}' "$TMP_DIR/$CHECKSUM")"
  ACTUAL="$(shasum -a 256 "$TMP_DIR/$ARTIFACT" | awk '{print $1}')"
  if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "SHA256 mismatch."
    exit 1
  fi
else
  echo "No SHA256 tool found (sha256sum/shasum)."
  exit 2
fi

TARGET_DIR="${INSTALL_ROOT}/${VERSION}"
mkdir -p "$TARGET_DIR"
tar -xzf "$TMP_DIR/$ARTIFACT" -C "$TARGET_DIR"

BOOTSTRAP_CTL="${TARGET_DIR}/scripts/skill-runnerctl"
BOOTSTRAP_EXIT_CODE="null"
if [ -x "$BOOTSTRAP_CTL" ]; then
  if [ "$JSON_OUTPUT" -eq 1 ]; then
    if "$BOOTSTRAP_CTL" bootstrap --json >/dev/null; then
      BOOTSTRAP_EXIT_CODE=0
    else
      BOOTSTRAP_EXIT_CODE=$?
      echo "WARNING: bootstrap failed; installation will continue. Check bootstrap diagnostics logs." >&2
    fi
  else
    echo "Running bootstrap (same strategy as agent_manager --ensure)..."
    if "$BOOTSTRAP_CTL" bootstrap --json; then
      BOOTSTRAP_EXIT_CODE=0
    else
      BOOTSTRAP_EXIT_CODE=$?
      echo "WARNING: bootstrap failed; installation will continue. Check bootstrap diagnostics logs."
    fi
  fi
else
  if [ "$JSON_OUTPUT" -eq 1 ]; then
    echo "WARNING: bootstrap script not found at ${BOOTSTRAP_CTL}; installation will continue without bootstrap." >&2
  else
    echo "WARNING: bootstrap script not found at ${BOOTSTRAP_CTL}; installation will continue without bootstrap."
  fi
fi

if [ "$JSON_OUTPUT" -eq 1 ]; then
  ESCAPED_TARGET_DIR="$(printf '%s' "$TARGET_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  ESCAPED_VERSION="$(printf '%s' "$VERSION" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  printf '{"ok":true,"install_dir":"%s","version":"%s","bootstrap_exit_code":%s}\n' \
    "$ESCAPED_TARGET_DIR" \
    "$ESCAPED_VERSION" \
    "$BOOTSTRAP_EXIT_CODE"
else
  echo "Installed to: ${TARGET_DIR}"
  echo "Next:"
  echo "  ${TARGET_DIR}/scripts/skill-runnerctl install --json"
  echo "  ${TARGET_DIR}/scripts/skill-runnerctl up --mode local --json"
fi
