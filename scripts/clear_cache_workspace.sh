#!/bin/bash
# Wrapper to clear cache using the workspace data dir (same as integration/e2e tests)

export SKILL_RUNNER_DATA_DIR="/home/joshua/Workspace/Code/Skill-Runner/data"
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Skill Runner Clear Cache (Workspace) ==="
echo "Data Dir: $SKILL_RUNNER_DATA_DIR"
echo "==========================================="

exec python scripts/clear_cache.py
