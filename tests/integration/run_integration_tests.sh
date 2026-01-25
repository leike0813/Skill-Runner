#!/bin/bash
# run_integration_tests.sh - Wrapper for Integration Tests (tests/integration/run_integration_tests.py) with environment setup

# 1. Environment Setup
export SKILL_RUNNER_DATA_DIR="/home/joshua/Workspace/Code/Skill-Runner/data"
export UV_CACHE_DIR="/home/joshua/Workspace/Code/Skill-Runner/uv_cache"
export UV_PROJECT_ENVIRONMENT="/home/joshua/Workspace/Code/Skill-Runner/.venv"

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
# We forward all arguments ($@) to run_integration_tests.py so users can use flags like -k, -e, -v.

echo "Executing: uv run --extra dev python tests/integration/run_integration_tests.py $@"
exec uv run --extra dev python tests/integration/run_integration_tests.py "$@"
