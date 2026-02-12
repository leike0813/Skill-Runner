#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

export UI_BASIC_AUTH_ENABLED="${UI_BASIC_AUTH_ENABLED:-true}"
export UI_BASIC_AUTH_USERNAME="${UI_BASIC_AUTH_USERNAME:-admin}"
export UI_BASIC_AUTH_PASSWORD="${UI_BASIC_AUTH_PASSWORD:-change-me}"

echo "=== Skill Runner (UI Auth) ==="
echo "Root: ${ROOT_DIR}"
echo "Host: ${HOST}"
echo "Port: ${PORT}"
echo "UI_BASIC_AUTH_ENABLED=${UI_BASIC_AUTH_ENABLED}"
echo "UI_BASIC_AUTH_USERNAME=${UI_BASIC_AUTH_USERNAME}"
echo "UI_BASIC_AUTH_PASSWORD=********"
echo "=============================="

cd "${ROOT_DIR}"
exec conda run --no-capture-output -n DataProcessing python -u -m uvicorn server.main:app --host "${HOST}" --port "${PORT}"
