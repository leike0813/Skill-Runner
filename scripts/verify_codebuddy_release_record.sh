#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RECORD="artifacts/archive/codebuddy_release_gate.json"
SCHEMA="server/engines/codebuddy/schemas/release_gate.schema.json"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ ! -f "$RECORD" ]]; then
  echo "CodeBuddy release record is missing: $RECORD" >&2
  exit 1
fi

"$PYTHON_BIN" - "$SCHEMA" "$RECORD" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

schema_path = Path(sys.argv[1])
record_path = Path(sys.argv[2])
schema = json.loads(schema_path.read_text(encoding="utf-8"))
record = json.loads(record_path.read_text(encoding="utf-8"))
jsonschema.validate(record, schema)
PY

"$PYTHON_BIN" scripts/scan_codebuddy_secrets.py "$RECORD"
