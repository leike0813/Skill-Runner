#!/usr/bin/env sh
set -e

MODE="${1:---check}"
TARGET_ENGINE="${2:-}"
DATA_DIR="${SKILL_RUNNER_DATA_DIR:-/data}"
STATUS_FILE="${DATA_DIR}/agent_status.json"

log() {
  printf "%s\n" "$*"
}

check_cmd() {
  cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "true"
  else
    printf "false"
  fi
}

read_version() {
  cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    "$cmd" --version 2>/dev/null | head -n 1
  else
    printf ""
  fi
}

ensure_dirs() {
  mkdir -p "${DATA_DIR}"
}

install_cli() {
  pkg="$1"
  log "Installing ${pkg}..."
  npm install -g "${pkg}" || return 1
}

render_status() {
  codex_present="$(check_cmd codex)"
  gemini_present="$(check_cmd gemini)"
  iflow_present="$(check_cmd iflow)"

  codex_ver="$(read_version codex)"
  gemini_ver="$(read_version gemini)"
  iflow_ver="$(read_version iflow)"

  cat <<EOF
{
  "codex": {"present": ${codex_present}, "version": "$(printf "%s" "${codex_ver}")"},
  "gemini": {"present": ${gemini_present}, "version": "$(printf "%s" "${gemini_ver}")"},
  "iflow": {"present": ${iflow_present}, "version": "$(printf "%s" "${iflow_ver}")"}
}
EOF
}

ensure_agents() {
  if [ "$(check_cmd codex)" = "false" ]; then
    install_cli "@openai/codex" || log "WARN: Failed to install @openai/codex"
  fi
  if [ "$(check_cmd gemini)" = "false" ]; then
    install_cli "@google/gemini-cli" || log "WARN: Failed to install @google/gemini-cli"
  fi
  if [ "$(check_cmd iflow)" = "false" ]; then
    install_cli "@iflow-ai/iflow-cli" || log "WARN: Failed to install @iflow-ai/iflow-cli"
  fi
}

upgrade_agents() {
  install_cli "@openai/codex" || log "WARN: Failed to upgrade @openai/codex"
  install_cli "@google/gemini-cli" || log "WARN: Failed to upgrade @google/gemini-cli"
  install_cli "@iflow-ai/iflow-cli" || log "WARN: Failed to upgrade @iflow-ai/iflow-cli"
}

upgrade_single_engine() {
  engine="$1"
  case "$engine" in
    codex)
      install_cli "@openai/codex"
      ;;
    gemini)
      install_cli "@google/gemini-cli"
      ;;
    iflow)
      install_cli "@iflow-ai/iflow-cli"
      ;;
    *)
      log "Unsupported engine: ${engine}"
      return 1
      ;;
  esac
}

ensure_dirs

case "${MODE}" in
  --ensure)
    ensure_agents
    ;;
  --upgrade)
    upgrade_agents
    ;;
  --upgrade-engine)
    if [ -z "${TARGET_ENGINE}" ]; then
      log "Usage: $0 --upgrade-engine <codex|gemini|iflow>"
      exit 1
    fi
    upgrade_single_engine "${TARGET_ENGINE}"
    ;;
  --check)
    ;;
  *)
    log "Unknown mode: ${MODE}"
    log "Usage: $0 [--check|--ensure|--upgrade|--upgrade-engine <engine>]"
    exit 1
    ;;
esac

render_status > "${STATUS_FILE}"
log "Agent status written to ${STATUS_FILE}"
