#!/bin/bash
# Wrapper for API integration tests (in-process FastAPI/TestClient).

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_CONFIG_FILE="$PROJECT_ROOT/tests/config/test_env.sh"
if [[ ! -f "$ENV_CONFIG_FILE" ]]; then
  echo "Missing test env config: $ENV_CONFIG_FILE" >&2
  exit 1
fi

source "$ENV_CONFIG_FILE"
load_skill_runner_test_env "$PROJECT_ROOT"

echo "Executing: conda run --no-capture-output -n DataProcessing python -u -m pytest tests/api_integration $@"
exec conda run --no-capture-output -n DataProcessing python -u -m pytest tests/api_integration "$@"
