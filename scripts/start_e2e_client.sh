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
LOCAL_ROOT="${SKILL_RUNNER_LOCAL_ROOT:-$HOME/.local/share/skill-runner}"

export SKILL_RUNNER_AGENT_CACHE_DIR="${SKILL_RUNNER_AGENT_CACHE_DIR:-$LOCAL_ROOT/agent-cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SKILL_RUNNER_AGENT_CACHE_DIR/uv_venv}"

export SKILL_RUNNER_E2E_CLIENT_HOST="${SKILL_RUNNER_E2E_CLIENT_HOST:-${HOST}}"
export SKILL_RUNNER_E2E_CLIENT_PORT="${SKILL_RUNNER_E2E_CLIENT_PORT:-${PORT}}"
export SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL="${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL:-http://127.0.0.1:8000}"

mkdir -p "$SKILL_RUNNER_AGENT_CACHE_DIR"

echo "=== Skill Runner E2E Example Client ==="
echo "Project Root: ${PROJECT_ROOT}"
echo "Host: ${SKILL_RUNNER_E2E_CLIENT_HOST}"
echo "Port: ${SKILL_RUNNER_E2E_CLIENT_PORT}"
echo "Backend: ${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL}"
echo "UV Venv Dir: ${UV_PROJECT_ENVIRONMENT}"
echo "======================================="

cd "${PROJECT_ROOT}"
exec uv run python -m e2e_client.app
