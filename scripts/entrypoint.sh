#!/usr/bin/env sh
set -e

echo "=== Skill Runner Container ==="
echo "Runtime Mode: ${SKILL_RUNNER_RUNTIME_MODE:-auto}"
echo "Data Dir: ${SKILL_RUNNER_DATA_DIR:-/data}"
echo "Agent Cache Dir: ${SKILL_RUNNER_AGENT_CACHE_DIR:-/opt/cache/skill-runner}"
echo "Agent Home: ${SKILL_RUNNER_AGENT_HOME:-/opt/cache/skill-runner/agent-home}"
echo "NPM Prefix: ${SKILL_RUNNER_NPM_PREFIX:-${NPM_CONFIG_PREFIX:-/opt/cache/skill-runner/npm}}"
echo "UV Cache Dir: ${UV_CACHE_DIR:-/opt/cache/skill-runner/uv_cache}"
echo "UV Venv Dir: ${UV_PROJECT_ENVIRONMENT:-/opt/cache/skill-runner/uv_venv}"

kernel_version="$(uname -r | cut -d- -f1)"
kernel_major="$(printf '%s' "$kernel_version" | cut -d. -f1)"
kernel_minor="$(printf '%s' "$kernel_version" | cut -d. -f2)"
landlock_enabled=0
if [ "${kernel_major:-0}" -gt 5 ] || { [ "${kernel_major:-0}" -eq 5 ] && [ "${kernel_minor:-0}" -ge 13 ]; }; then
  landlock_enabled=1
fi
export LANDLOCK_ENABLED="${landlock_enabled}"
echo "Landlock Enabled: ${LANDLOCK_ENABLED} (kernel ${kernel_version})"

python3 /app/scripts/agent_manager.py --ensure || true

if [ -d "/opt/config" ]; then
  echo "Importing auth credentials from /opt/config (settings are ignored by design)..."
  python3 /app/scripts/agent_manager.py --import-credentials /opt/config || true
fi

python3 -c '
from pathlib import Path
from server.config import config
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager

runs_parent = Path(config.SYSTEM.RUNS_DIR).resolve()
runs_parent.mkdir(parents=True, exist_ok=True)
run_folder_trust_manager.bootstrap_parent_trust(runs_parent)
print(f"Bootstrapped trust for runs parent: {runs_parent}")
'

exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
