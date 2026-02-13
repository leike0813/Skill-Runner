#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

MODE="${1:-local}"

echo "=== Skill Runner Agent CLI Upgrade ==="

if [ "${MODE}" = "container" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker not found"
    exit 1
  fi
  if ! command -v docker compose >/dev/null 2>&1; then
    echo "docker compose not found"
    exit 1
  fi
  docker compose run --rm api sh -lc "python3 /app/scripts/agent_manager.py --upgrade"
  echo "Container upgrade done."
  exit 0
fi

python3 "${SCRIPT_DIR}/agent_manager.py" --upgrade
echo "Local upgrade done."
