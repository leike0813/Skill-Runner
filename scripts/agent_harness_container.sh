#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose not found"
  exit 1
fi

cd "${PROJECT_ROOT}"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx "api"; then
  echo "docker compose service 'api' is not running"
  exit 1
fi

if [ -t 0 ] && [ -t 1 ] && [ -t 2 ]; then
  exec docker compose exec api agent-harness "$@"
fi

exec docker compose exec -T api agent-harness "$@"
