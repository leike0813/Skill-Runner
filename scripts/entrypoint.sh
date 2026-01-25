#!/usr/bin/env sh
set -e

echo "=== Skill Runner Container ==="
echo "Data Dir: ${SKILL_RUNNER_DATA_DIR:-/data}"
echo "Skills Dir: /app/skills"
echo "Config Dir (HOME): ${HOME:-/root}"
echo "Agents Prefix: ${NPM_CONFIG_PREFIX:-/opt/cache/npm}"
echo "UV Cache Dir: ${UV_CACHE_DIR:-/opt/cache/uv_cache}"
echo "UV Venv Dir: ${UV_PROJECT_ENVIRONMENT:-/opt/cache/uv_venv}"

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
fi

if [ -x "/app/scripts/agent_manager.sh" ]; then
  /app/scripts/agent_manager.sh --ensure || true
fi

exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8000}"
