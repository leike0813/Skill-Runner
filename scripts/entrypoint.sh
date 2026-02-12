#!/usr/bin/env sh
set -e

echo "=== Skill Runner Container ==="
echo "Data Dir: ${SKILL_RUNNER_DATA_DIR:-/data}"
echo "Skills Dir: /app/skills"
echo "Config Dir (HOME): ${HOME:-/root}"
echo "Agents Prefix: ${NPM_CONFIG_PREFIX:-/opt/cache/npm}"
echo "UV Cache Dir: ${UV_CACHE_DIR:-/opt/cache/uv_cache}"
echo "UV Venv Dir: ${UV_PROJECT_ENVIRONMENT:-/opt/cache/uv_venv}"

kernel_version="$(uname -r | cut -d- -f1)"
kernel_major="$(printf '%s' "$kernel_version" | cut -d. -f1)"
kernel_minor="$(printf '%s' "$kernel_version" | cut -d. -f2)"
landlock_enabled=0
if [ "${kernel_major:-0}" -gt 5 ] || { [ "${kernel_major:-0}" -eq 5 ] && [ "${kernel_minor:-0}" -ge 13 ]; }; then
  landlock_enabled=1
fi
export LANDLOCK_ENABLED="${landlock_enabled}"
echo "Landlock Enabled: ${LANDLOCK_ENABLED} (kernel ${kernel_version})"

if [ -d "/opt/config" ]; then
  mkdir -p /opt/config/codex /opt/config/gemini /opt/config/iflow
  ln -sfn /opt/config/codex /root/.codex
  ln -sfn /opt/config/gemini /root/.gemini
  ln -sfn /opt/config/iflow /root/.iflow

  if [ ! -f "/opt/config/gemini/settings.json" ]; then
    cat <<'EOF' > /opt/config/gemini/settings.json
{
  "security": {
    "auth": {
      "selectedType": "oauth-personal"
    }
  }
}
EOF
  fi

  if [ ! -f "/opt/config/iflow/settings.json" ]; then
    cat <<'EOF' > /opt/config/iflow/settings.json
{
  "selectedAuthType": "iflow"
}
EOF
  fi

  if [ ! -f "/opt/config/codex/config.toml" ]; then
    cat <<'EOF' > /opt/config/codex/config.toml
cli_auth_credentials_store = "file"
EOF
  fi

  runs_parent="$(python3 -c "from pathlib import Path; import os; print(Path(os.environ.get('SKILL_RUNNER_DATA_DIR', '/data')).joinpath('runs').resolve())")"
  mkdir -p "${runs_parent}"

  codex_trust_line="projects.\"${runs_parent}\".trust_level = \"trusted\""
  if ! grep -Fqx "${codex_trust_line}" /opt/config/codex/config.toml; then
    printf "\n%s\n" "${codex_trust_line}" >> /opt/config/codex/config.toml
  fi

  python3 -c '
import json
import shutil
import sys
from pathlib import Path

trusted_path = Path("/opt/config/gemini/trustedFolders.json")
runs_parent = Path(sys.argv[1]).resolve().as_posix()

payload = {}
if trusted_path.exists():
    try:
        payload = json.loads(trusted_path.read_text(encoding="utf-8"))
    except Exception:
        backup = trusted_path.with_name(f"{trusted_path.name}.bak")
        shutil.copy2(trusted_path, backup)
        payload = {}
if not isinstance(payload, dict):
    if trusted_path.exists():
        backup = trusted_path.with_name(f"{trusted_path.name}.bak")
        shutil.copy2(trusted_path, backup)
    payload = {}

payload[runs_parent] = "TRUST_FOLDER"
trusted_path.parent.mkdir(parents=True, exist_ok=True)
trusted_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
' "${runs_parent}"
fi

if [ -x "/app/scripts/agent_manager.sh" ]; then
  /app/scripts/agent_manager.sh --ensure || true
fi

exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
