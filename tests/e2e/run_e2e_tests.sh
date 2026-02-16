#!/bin/bash
# run_e2e_tests.sh - Wrapper for REST E2E Tests (tests/e2e/run_e2e_tests.py)

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_CONFIG_FILE="$PROJECT_ROOT/tests/config/test_env.sh"
if [[ ! -f "$ENV_CONFIG_FILE" ]]; then
  echo "Missing test env config: $ENV_CONFIG_FILE" >&2
  exit 1
fi
source "$ENV_CONFIG_FILE"
load_skill_runner_test_env "$PROJECT_ROOT"

echo "=== Skill Runner REST E2E Test Environment ==="
echo "Data Dir: $SKILL_RUNNER_DATA_DIR"
echo "UV Cache: $UV_CACHE_DIR"
echo "UV Venv:  $UV_PROJECT_ENVIRONMENT"
echo "==============================================="

mkdir -p "$SKILL_RUNNER_DATA_DIR/runs"

echo "Executing: uv run --extra dev python tests/e2e/run_e2e_tests.py $@"
exec uv run --extra dev python tests/e2e/run_e2e_tests.py "$@"
