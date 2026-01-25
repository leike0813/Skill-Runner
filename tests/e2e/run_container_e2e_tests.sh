#!/bin/bash
# run_container_e2e_tests.sh - Wrapper for container REST E2E Tests (tests/e2e/run_container_e2e_tests.py)

export UV_CACHE_DIR="/home/joshua/Workspace/Code/Skill-Runner/uv_cache"
export UV_PROJECT_ENVIRONMENT="/home/joshua/Workspace/Code/Skill-Runner/.venv"

echo "Executing: uv run --extra dev python tests/e2e/run_container_e2e_tests.py $@"
exec uv run --extra dev python tests/e2e/run_container_e2e_tests.py "$@"
