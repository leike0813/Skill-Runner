#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Please install uv first: https://docs.astral.sh/uv/"
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8011}"

export SKILL_RUNNER_E2E_CLIENT_HOST="${SKILL_RUNNER_E2E_CLIENT_HOST:-${HOST}}"
export SKILL_RUNNER_E2E_CLIENT_PORT="${SKILL_RUNNER_E2E_CLIENT_PORT:-${PORT}}"
export SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL="${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL:-http://127.0.0.1:8000}"

echo "=== Skill Runner E2E Example Client ==="
echo "Project Root: ${PROJECT_ROOT}"
echo "Host: ${SKILL_RUNNER_E2E_CLIENT_HOST}"
echo "Port: ${SKILL_RUNNER_E2E_CLIENT_PORT}"
echo "Backend: ${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL}"
echo "======================================="

cd "${PROJECT_ROOT}"
exec uv run python -m e2e_client.app
