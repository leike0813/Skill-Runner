#!/usr/bin/env sh
set -e

echo "=== Skill Runner E2E Client Container ==="
echo "Runtime Mode: ${SKILL_RUNNER_RUNTIME_MODE:-container}"
echo "Host: ${SKILL_RUNNER_E2E_CLIENT_HOST:-0.0.0.0}"
echo "Port: ${SKILL_RUNNER_E2E_CLIENT_PORT:-8011}"
echo "Backend Base URL: ${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL:-http://api:8000}"

export SKILL_RUNNER_E2E_CLIENT_HOST="${SKILL_RUNNER_E2E_CLIENT_HOST:-0.0.0.0}"
export SKILL_RUNNER_E2E_CLIENT_PORT="${SKILL_RUNNER_E2E_CLIENT_PORT:-8011}"
export SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL="${SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL:-http://api:8000}"

exec python3 -u -m e2e_client.app
