#!/bin/bash
# Shared test environment defaults for E2E and integration wrappers.
# Usage:
#   source tests/config/test_env.sh
#   load_skill_runner_test_env "$PROJECT_ROOT"

load_skill_runner_test_env() {
  local project_root="$1"
  if [[ -z "$project_root" ]]; then
    echo "load_skill_runner_test_env: project_root is required" >&2
    return 1
  fi

  local artifact_root_default
  if artifact_root_default="$(CDPATH= cd -- "${project_root}/../../../Artifact/Skill-Runner/" 2>/dev/null && pwd)"; then
    :
  else
    artifact_root_default="$project_root"
  fi

  # Keep one shared root for test artifacts/cache/venv unless caller overrides.
  export SKILL_RUNNER_TEST_ARTIFACT_ROOT="${SKILL_RUNNER_TEST_ARTIFACT_ROOT:-$artifact_root_default}"

  # Shared directories (E2E defaults as baseline).
  export SKILL_RUNNER_DATA_DIR="${SKILL_RUNNER_DATA_DIR:-$SKILL_RUNNER_TEST_ARTIFACT_ROOT/data}"
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$SKILL_RUNNER_TEST_ARTIFACT_ROOT/uv_cache}"
  export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SKILL_RUNNER_TEST_ARTIFACT_ROOT/.venv}"
  export E2E_DOWNLOAD_DIR="${E2E_DOWNLOAD_DIR:-${SKILL_RUNNER_E2E_DOWNLOAD_DIR:-$SKILL_RUNNER_TEST_ARTIFACT_ROOT/e2e-test-download}}"
}
