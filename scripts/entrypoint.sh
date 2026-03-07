#!/usr/bin/env sh
set -e

DATA_DIR="${SKILL_RUNNER_DATA_DIR:-/data}"
BOOTSTRAP_LOG_DIR="${DATA_DIR}/logs"
BOOTSTRAP_LOG_FILE="${BOOTSTRAP_LOG_DIR}/bootstrap.log"
BOOTSTRAP_REPORT_FILE="${DATA_DIR}/agent_bootstrap_report.json"
BOOTSTRAP_LOG_MAX_BYTES="${SKILL_RUNNER_BOOTSTRAP_LOG_MAX_BYTES:-1048576}"
BOOTSTRAP_LOG_BACKUP_COUNT="${SKILL_RUNNER_BOOTSTRAP_LOG_BACKUP_COUNT:-3}"

mkdir -p "${BOOTSTRAP_LOG_DIR}"

rotate_bootstrap_log_if_needed() {
  if [ ! -f "${BOOTSTRAP_LOG_FILE}" ]; then
    return 0
  fi
  file_size="$(wc -c < "${BOOTSTRAP_LOG_FILE}" | tr -d ' ' || echo 0)"
  if [ "${file_size}" -lt "${BOOTSTRAP_LOG_MAX_BYTES}" ]; then
    return 0
  fi

  idx="${BOOTSTRAP_LOG_BACKUP_COUNT}"
  while [ "${idx}" -ge 1 ]; do
    current="${BOOTSTRAP_LOG_FILE}.${idx}"
    if [ -f "${current}" ]; then
      if [ "${idx}" -eq "${BOOTSTRAP_LOG_BACKUP_COUNT}" ]; then
        rm -f "${current}"
      else
        next_idx=$((idx + 1))
        mv "${current}" "${BOOTSTRAP_LOG_FILE}.${next_idx}"
      fi
    fi
    idx=$((idx - 1))
  done
  mv "${BOOTSTRAP_LOG_FILE}" "${BOOTSTRAP_LOG_FILE}.1"
}

bootstrap_log_event() {
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  line="ts=${ts} $*"
  echo "${line}"
  rotate_bootstrap_log_if_needed
  printf "%s\n" "${line}" >> "${BOOTSTRAP_LOG_FILE}"
}

bootstrap_log_event "event=bootstrap.start phase=container_start outcome=running data_dir=${DATA_DIR}"

echo "=== Skill Runner Container ==="
echo "Runtime Mode: ${SKILL_RUNNER_RUNTIME_MODE:-auto}"
echo "Data Dir: ${DATA_DIR}"
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
bootstrap_log_event "event=bootstrap.runtime_summary phase=container_start outcome=ok landlock_enabled=${LANDLOCK_ENABLED} kernel=${kernel_version}"

bootstrap_log_event "event=agent.ensure.start phase=agent_ensure outcome=running"
ensure_started_sec="$(date +%s)"
python3 /app/scripts/agent_manager.py --ensure --bootstrap-report-file "${BOOTSTRAP_REPORT_FILE}" || true
ensure_ended_sec="$(date +%s)"
ensure_duration_sec=$((ensure_ended_sec - ensure_started_sec))

ensure_outcome="$(python3 -c '
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    print("report_missing")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("report_unreadable")
    raise SystemExit(0)
summary = payload.get("summary") if isinstance(payload, dict) else {}
if not isinstance(summary, dict):
    print("unknown")
else:
    print(str(summary.get("outcome") or "unknown"))
' "${BOOTSTRAP_REPORT_FILE}" 2>/dev/null || echo "unknown")"
bootstrap_log_event "event=agent.ensure.done phase=agent_ensure outcome=${ensure_outcome} duration_sec=${ensure_duration_sec} report_file=${BOOTSTRAP_REPORT_FILE}"

if [ -d "/opt/config" ]; then
  bootstrap_log_event "event=agent.credentials_import.start phase=agent_credentials_import outcome=running source=/opt/config"
  echo "Importing auth credentials from /opt/config (settings are ignored by design)..."
  python3 /app/scripts/agent_manager.py --import-credentials /opt/config || true
  bootstrap_log_event "event=agent.credentials_import.done phase=agent_credentials_import outcome=ok source=/opt/config"
fi

bootstrap_log_event "event=bootstrap.trust_bootstrap.start phase=run_trust_bootstrap outcome=running"
python3 -c '
from pathlib import Path
from server.config import config
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager

runs_parent = Path(config.SYSTEM.RUNS_DIR).resolve()
runs_parent.mkdir(parents=True, exist_ok=True)
run_folder_trust_manager.bootstrap_parent_trust(runs_parent)
print(f"Bootstrapped trust for runs parent: {runs_parent}")
'
bootstrap_log_event "event=bootstrap.trust_bootstrap.done phase=run_trust_bootstrap outcome=ok"
bootstrap_log_event "event=bootstrap.handoff_uvicorn phase=container_start outcome=running"

exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
