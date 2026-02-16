#!/bin/bash
# run_local_e2e_tests.sh - Start local deploy chain and run REST E2E tests against it.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_CONFIG_FILE="$PROJECT_ROOT/tests/config/test_env.sh"
if [[ ! -f "$ENV_CONFIG_FILE" ]]; then
  echo "Missing test env config: $ENV_CONFIG_FILE" >&2
  exit 1
fi
source "$ENV_CONFIG_FILE"
load_skill_runner_test_env "$PROJECT_ROOT"

echo "=== Skill Runner Local E2E Environment ==="
echo "E2E Download Dir: $E2E_DOWNLOAD_DIR"
echo "UV Cache:         $UV_CACHE_DIR"
echo "UV Venv:          $UV_PROJECT_ENVIRONMENT"
echo "========================================="

echo "Executing: uv run --extra dev python tests/e2e/run_local_e2e_tests.py $@"
exec uv run --extra dev python tests/e2e/run_local_e2e_tests.py "$@"
