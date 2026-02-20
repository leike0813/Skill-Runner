#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found. Please install conda and ensure it is in PATH."
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8011}"

export SKILL_RUNNER_E2E_CLIENT_HOST="${SKILL_RUNNER_E2E_CLIENT_HOST:-${HOST}}"
export SKILL_RUNNER_E2E_CLIENT_PORT="${SKILL_RUNNER_E2E_CLIENT_PORT:-${PORT}}"
export SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL="${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL:-http://127.0.0.1:8000}"

echo "=== Skill Runner E2E Example Client ==="
echo "Root: ${ROOT_DIR}"
echo "Host: ${SKILL_RUNNER_E2E_CLIENT_HOST}"
echo "Port: ${SKILL_RUNNER_E2E_CLIENT_PORT}"
echo "Backend: ${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL}"
echo "======================================="

cd "${ROOT_DIR}"
exec conda run --no-capture-output -n DataProcessing python -u -m e2e_client.app

