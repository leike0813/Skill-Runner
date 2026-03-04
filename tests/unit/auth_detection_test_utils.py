from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "auth_detection_samples"


def load_manifest() -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def sample_dir(engine: str, sample_id: str) -> Path:
    return FIXTURE_ROOT / engine / sample_id


def load_sample(engine: str, sample_id: str) -> dict[str, Any]:
    root = sample_dir(engine, sample_id)
    pty_path = root / "pty-output.1.log"
    payload: dict[str, Any] = {
        "root": root,
        "context": json.loads((root / "context.json").read_text(encoding="utf-8")),
        "meta": json.loads((root / "meta.1.json").read_text(encoding="utf-8")),
        "stdout": (root / "stdout.1.log").read_text(encoding="utf-8"),
        "stderr": (root / "stderr.1.log").read_text(encoding="utf-8"),
        "pty_output": pty_path.read_text(encoding="utf-8") if pty_path.exists() else "",
        "parser_diagnostics": (root / "parser_diagnostics.1.jsonl").read_text(encoding="utf-8"),
    }
    return payload
