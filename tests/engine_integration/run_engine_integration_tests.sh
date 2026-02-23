#!/bin/bash
# run_engine_integration_tests.sh - Wrapper for engine integration suites with environment setup

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_CONFIG_FILE="$PROJECT_ROOT/tests/config/test_env.sh"
if [[ ! -f "$ENV_CONFIG_FILE" ]]; then
  echo "Missing test env config: $ENV_CONFIG_FILE" >&2
  exit 1
fi

# 1. Environment Setup (shared with E2E wrappers)
source "$ENV_CONFIG_FILE"
load_skill_runner_test_env "$PROJECT_ROOT"

# Confirm Environment
echo "=== Skill Runner Integration Test Environment ==="
echo "Data Dir: $SKILL_RUNNER_DATA_DIR"
echo "UV Cache: $UV_CACHE_DIR"
echo "UV Venv:  $UV_PROJECT_ENVIRONMENT"
echo "==============================================="

# Ensure data directory exists
mkdir -p "$SKILL_RUNNER_DATA_DIR/runs"

# 2. Execute Runner
# We use 'uv run' to ensure dependencies are loaded from the project environment.
# We forward all arguments ($@) to run_engine_integration_tests.py so users can use flags like -k, -e, -v.

echo "Executing: uv run --extra dev python tests/engine_integration/run_engine_integration_tests.py $@"
exec uv run --extra dev python tests/engine_integration/run_engine_integration_tests.py "$@"
