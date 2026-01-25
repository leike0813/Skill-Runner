#!/bin/bash
# run_e2e_tests.sh - Wrapper for REST E2E Tests (tests/e2e/run_e2e_tests.py)

export SKILL_RUNNER_DATA_DIR="/home/joshua/Workspace/Code/Skill-Runner/data"
export UV_CACHE_DIR="/home/joshua/Workspace/Code/Skill-Runner/uv_cache"
export UV_PROJECT_ENVIRONMENT="/home/joshua/Workspace/Code/Skill-Runner/.venv"

echo "=== Skill Runner REST E2E Test Environment ==="
echo "Data Dir: $SKILL_RUNNER_DATA_DIR"
echo "UV Cache: $UV_CACHE_DIR"
echo "UV Venv:  $UV_PROJECT_ENVIRONMENT"
echo "==============================================="

mkdir -p "$SKILL_RUNNER_DATA_DIR/runs"

echo "Executing: uv run --extra dev python tests/e2e/run_e2e_tests.py $@"
exec uv run --extra dev python tests/e2e/run_e2e_tests.py "$@"
