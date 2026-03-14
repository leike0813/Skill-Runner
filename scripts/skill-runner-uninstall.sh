#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

JSON_OUTPUT=0
CLEAR_DATA=0
CLEAR_AGENT_HOME=0
LOCAL_ROOT="${SKILL_RUNNER_LOCAL_ROOT:-$HOME/.local/share/skill-runner}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --clear-data)
      CLEAR_DATA=1
      shift
      ;;
    --clear-agent-home)
      CLEAR_AGENT_HOME=1
      shift
      ;;
    --json)
      JSON_OUTPUT=1
      shift
      ;;
    --local-root)
      if [ "$#" -lt 2 ]; then
        echo "--local-root requires a value" >&2
        exit 2
      fi
      LOCAL_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

normalize_path() {
  input="$1"
  if [ -z "$input" ]; then
    printf '%s' ""
    return
  fi
  if [ "$input" = "/" ]; then
    printf '%s' "/"
    return
  fi
  case "$input" in
    /*) normalized="$input" ;;
    *) normalized="$PWD/$input" ;;
  esac
  while [ "${normalized%/}" != "$normalized" ]; do
    normalized="${normalized%/}"
  done
  printf '%s' "$normalized"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g'
}

append_line() {
  file="$1"
  value="$2"
  printf '%s\n' "$value" >>"$file"
}

json_array_from_file() {
  file="$1"
  output="["
  first=1
  while IFS= read -r line || [ -n "$line" ]; do
    escaped="$(json_escape "$line")"
    if [ "$first" -eq 0 ]; then
      output="$output,"
    fi
    output="$output\"$escaped\""
    first=0
  done <"$file"
  output="$output]"
  printf '%s' "$output"
}

is_under_local_root() {
  candidate="$1"
  case "$candidate" in
    "$LOCAL_ROOT" | "$LOCAL_ROOT"/*) return 0 ;;
    *) return 1 ;;
  esac
}

remove_managed_path() {
  target="$(normalize_path "$1")"
  if [ -z "$target" ] || [ "$target" = "/" ]; then
    append_line "$FAILED_FILE" "$1"
    return
  fi
  if ! is_under_local_root "$target"; then
    append_line "$FAILED_FILE" "$target"
    return
  fi
  if [ ! -e "$target" ]; then
    append_line "$PRESERVED_FILE" "$target"
    return
  fi
  if rm -rf "$target" 2>/dev/null; then
    append_line "$REMOVED_FILE" "$target"
  else
    append_line "$FAILED_FILE" "$target"
  fi
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
REMOVED_FILE="$TMP_DIR/removed_paths.txt"
FAILED_FILE="$TMP_DIR/failed_paths.txt"
PRESERVED_FILE="$TMP_DIR/preserved_paths.txt"
DOWN_STDOUT_FILE="$TMP_DIR/down_stdout.txt"
DOWN_STDERR_FILE="$TMP_DIR/down_stderr.txt"
touch "$REMOVED_FILE" "$FAILED_FILE" "$PRESERVED_FILE" "$DOWN_STDOUT_FILE" "$DOWN_STDERR_FILE"

LOCAL_ROOT="$(normalize_path "$LOCAL_ROOT")"
if [ -z "$LOCAL_ROOT" ] || [ "$LOCAL_ROOT" = "/" ]; then
  append_line "$FAILED_FILE" "$LOCAL_ROOT"
fi

CTL_PATH="${SKILL_RUNNER_CTL_PATH:-$SCRIPT_DIR/skill-runnerctl}"
DOWN_OK=false
DOWN_EXIT=127
if [ -x "$CTL_PATH" ]; then
  if "$CTL_PATH" down --mode local --json >"$DOWN_STDOUT_FILE" 2>"$DOWN_STDERR_FILE"; then
    DOWN_OK=true
    DOWN_EXIT=0
  else
    DOWN_EXIT=$?
  fi
else
  printf 'skill-runnerctl not found or not executable: %s\n' "$CTL_PATH" >"$DOWN_STDERR_FILE"
fi

RELEASES_DIR="$(normalize_path "$LOCAL_ROOT/releases")"
AGENT_CACHE_DIR="$(normalize_path "$LOCAL_ROOT/agent-cache")"
DATA_DIR="$(normalize_path "$LOCAL_ROOT/data")"
AGENT_HOME_DIR="$(normalize_path "$AGENT_CACHE_DIR/agent-home")"
NPM_DIR="$(normalize_path "$AGENT_CACHE_DIR/npm")"
UV_CACHE_DIR="$(normalize_path "$AGENT_CACHE_DIR/uv_cache")"
UV_VENV_DIR="$(normalize_path "$AGENT_CACHE_DIR/uv_venv")"

if [ -n "$LOCAL_ROOT" ] && [ "$LOCAL_ROOT" != "/" ]; then
  remove_managed_path "$RELEASES_DIR"
  remove_managed_path "$NPM_DIR"
  remove_managed_path "$UV_CACHE_DIR"
  remove_managed_path "$UV_VENV_DIR"

  if [ "$CLEAR_DATA" -eq 1 ]; then
    remove_managed_path "$DATA_DIR"
  else
    append_line "$PRESERVED_FILE" "$DATA_DIR"
  fi

  if [ "$CLEAR_AGENT_HOME" -eq 1 ]; then
    remove_managed_path "$AGENT_HOME_DIR"
  else
    append_line "$PRESERVED_FILE" "$AGENT_HOME_DIR"
  fi

  if [ "$CLEAR_DATA" -eq 1 ] && [ "$CLEAR_AGENT_HOME" -eq 1 ]; then
    remove_managed_path "$LOCAL_ROOT"
  fi
fi

FAILED_COUNT="$(grep -c '.' "$FAILED_FILE" || true)"
if [ "${FAILED_COUNT:-0}" -gt 0 ]; then
  OK=false
  EXIT_CODE=1
  MESSAGE="Uninstall completed with errors."
else
  OK=true
  EXIT_CODE=0
  MESSAGE="Uninstall completed."
fi

REMOVED_JSON="$(json_array_from_file "$REMOVED_FILE")"
FAILED_JSON="$(json_array_from_file "$FAILED_FILE")"
PRESERVED_JSON="$(json_array_from_file "$PRESERVED_FILE")"
DOWN_STDOUT="$(cat "$DOWN_STDOUT_FILE" || true)"
DOWN_STDERR="$(cat "$DOWN_STDERR_FILE" || true)"
LOCAL_ROOT_ESCAPED="$(json_escape "$LOCAL_ROOT")"
MESSAGE_ESCAPED="$(json_escape "$MESSAGE")"
DOWN_STDOUT_ESCAPED="$(json_escape "$DOWN_STDOUT")"
DOWN_STDERR_ESCAPED="$(json_escape "$DOWN_STDERR")"

if [ "$JSON_OUTPUT" -eq 1 ]; then
  printf '{"ok":%s,"exit_code":%s,"message":"%s","local_root":"%s","removed_paths":%s,"failed_paths":%s,"preserved_paths":%s,"options":{"clear_data":%s,"clear_agent_home":%s},"down_result":{"invoked":true,"ok":%s,"exit_code":%s,"stdout":"%s","stderr":"%s"}}\n' \
    "$OK" \
    "$EXIT_CODE" \
    "$MESSAGE_ESCAPED" \
    "$LOCAL_ROOT_ESCAPED" \
    "$REMOVED_JSON" \
    "$FAILED_JSON" \
    "$PRESERVED_JSON" \
    "$([ "$CLEAR_DATA" -eq 1 ] && printf 'true' || printf 'false')" \
    "$([ "$CLEAR_AGENT_HOME" -eq 1 ] && printf 'true' || printf 'false')" \
    "$DOWN_OK" \
    "$DOWN_EXIT" \
    "$DOWN_STDOUT_ESCAPED" \
    "$DOWN_STDERR_ESCAPED"
  exit "$EXIT_CODE"
fi

echo "$MESSAGE"
echo "Local root: $LOCAL_ROOT"
echo "Down result: ok=$DOWN_OK exit_code=$DOWN_EXIT"
echo "Removed paths:"
cat "$REMOVED_FILE"
echo "Failed paths:"
cat "$FAILED_FILE"
echo "Preserved paths:"
cat "$PRESERVED_FILE"
exit "$EXIT_CODE"
