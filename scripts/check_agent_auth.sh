#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
MODE="${1:-local}"

if [ "${MODE}" = "container" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker not found"
    exit 1
  fi
  if ! command -v docker compose >/dev/null 2>&1; then
    echo "docker compose not found"
    exit 1
  fi
  docker compose run --rm api sh -lc "python3 /app/scripts/agent_manager.py --check-auth"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Please install uv first: https://docs.astral.sh/uv/"
  exit 1
fi

LOCAL_ROOT="${SKILL_RUNNER_LOCAL_ROOT:-$HOME/.local/share/skill-runner}"
export SKILL_RUNNER_RUNTIME_MODE="${SKILL_RUNNER_RUNTIME_MODE:-local}"
export SKILL_RUNNER_DATA_DIR="${SKILL_RUNNER_DATA_DIR:-$PROJECT_ROOT/data}"
export SKILL_RUNNER_AGENT_CACHE_DIR="${SKILL_RUNNER_AGENT_CACHE_DIR:-$LOCAL_ROOT/agent-cache}"
export SKILL_RUNNER_AGENT_HOME="${SKILL_RUNNER_AGENT_HOME:-$SKILL_RUNNER_AGENT_CACHE_DIR/agent-home}"
export SKILL_RUNNER_NPM_PREFIX="${SKILL_RUNNER_NPM_PREFIX:-$SKILL_RUNNER_AGENT_CACHE_DIR/npm}"
export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-$SKILL_RUNNER_NPM_PREFIX}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$SKILL_RUNNER_AGENT_CACHE_DIR/uv_cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SKILL_RUNNER_AGENT_CACHE_DIR/uv_venv}"

mkdir -p "$SKILL_RUNNER_DATA_DIR" "$SKILL_RUNNER_AGENT_CACHE_DIR" "$SKILL_RUNNER_AGENT_HOME"

cd "$PROJECT_ROOT"
uv run python scripts/agent_manager.py --check-auth

