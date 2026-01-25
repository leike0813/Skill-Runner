#!/usr/bin/env sh
set -e

echo "=== Skill Runner Agent CLI Upgrade ==="
echo "This script expects docker compose and a running build context."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if ! command -v docker compose >/dev/null 2>&1; then
  echo "docker compose not found"
  exit 1
fi

docker compose run --rm skill-runner sh -lc "/app/scripts/agent_manager.sh --upgrade"
echo "Done."
