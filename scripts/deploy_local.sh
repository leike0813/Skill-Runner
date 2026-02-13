#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Please install uv first: https://docs.astral.sh/uv/"
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "node not found. Please install Node.js 24+."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Please install npm."
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
export PATH="$SKILL_RUNNER_NPM_PREFIX/bin:$PATH"

mkdir -p "$SKILL_RUNNER_DATA_DIR" "$SKILL_RUNNER_AGENT_CACHE_DIR" "$SKILL_RUNNER_AGENT_HOME"

echo "=== Skill Runner Local Deploy ==="
echo "Project Root: $PROJECT_ROOT"
echo "Data Dir: $SKILL_RUNNER_DATA_DIR"
echo "Agent Cache Dir: $SKILL_RUNNER_AGENT_CACHE_DIR"
echo "Agent Home: $SKILL_RUNNER_AGENT_HOME"
echo "NPM Prefix: $SKILL_RUNNER_NPM_PREFIX"

cd "$PROJECT_ROOT"
uv run python scripts/agent_manager.py --ensure
uv run uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
