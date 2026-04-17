#!/bin/bash
# run_engine_integration_tests.sh - Wrapper for golden-driven engine integration pytest

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
echo "==============================================="

# Ensure data directory exists
mkdir -p "$SKILL_RUNNER_DATA_DIR/runs"

# 2. Execute Runner
# We use the shared DataProcessing conda environment and forward args to the
# compatibility shim, which in turn dispatches to pytest golden integration tests.

echo "Executing: conda run --no-capture-output -n DataProcessing python -u tests/engine_integration/run_engine_integration_tests.py $@"
exec conda run --no-capture-output -n DataProcessing python -u tests/engine_integration/run_engine_integration_tests.py "$@"
