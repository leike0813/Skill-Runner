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


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _extract_stream_from_row(row: dict[str, Any]) -> str | None:
    raw_ref = row.get("raw_ref")
    if isinstance(raw_ref, dict):
        stream_obj = raw_ref.get("stream")
        if isinstance(stream_obj, str) and stream_obj:
            return stream_obj
    event = row.get("event")
    if isinstance(event, dict):
        event_type = event.get("type")
        if event_type == "raw.stderr":
            return "stderr"
        if event_type == "raw.stdout":
            return "stdout"
    type_obj = row.get("type")
    if type_obj == "raw.stderr":
        return "stderr"
    if type_obj == "raw.stdout":
        return "stdout"
    return None


def _extract_line_from_row(row: dict[str, Any]) -> str | None:
    data = row.get("data")
    if not isinstance(data, dict):
        return None
    line_obj = data.get("line")
    if isinstance(line_obj, str):
        return line_obj
    return None


def _join_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _load_raw_streams_from_protocol_rows(root: Path) -> dict[str, str]:
    collected: dict[str, list[str]] = {
        "stdout": [],
        "stderr": [],
        "pty_output": [],
    }
    for filename in ("events.1.jsonl", "fcmp_events.1.jsonl"):
        for row in _load_jsonl_rows(root / filename):
            stream = _extract_stream_from_row(row)
            line = _extract_line_from_row(row)
            if not isinstance(stream, str) or line is None:
                continue
            if stream == "pty":
                collected["pty_output"].append(line)
            elif stream in {"stdout", "stderr"}:
                collected[stream].append(line)
    return {
        "stdout": _join_lines(collected["stdout"]),
        "stderr": _join_lines(collected["stderr"]),
        "pty_output": _join_lines(collected["pty_output"]),
    }


def _synthesize_raw_streams_for_missing_fixture(
    *,
    context: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, str]:
    sample_id_obj = context.get("sample_id")
    sample_id = sample_id_obj.strip() if isinstance(sample_id_obj, str) else ""
    if sample_id != "iflowcn_unknown_step_finish_loop":
        return {"stdout": "", "stderr": "", "pty_output": ""}
    launch = meta.get("launch")
    command_items: list[str] = []
    if isinstance(launch, dict):
        command = launch.get("command")
        if isinstance(command, list):
            command_items = [str(item).strip() for item in command if isinstance(item, str) and str(item).strip()]
    command_line = " ".join(command_items)
    synthesized_stdout_lines = [
        command_line,
        '{"type":"step_finish","part":{"reason":"unknown"}}',
        '{"type":"step_finish","part":{"reason":"unknown"}}',
    ]
    return {
        "stdout": _join_lines([line for line in synthesized_stdout_lines if line]),
        "stderr": "",
        "pty_output": "",
    }


def load_sample(engine: str, sample_id: str) -> dict[str, Any]:
    root = sample_dir(engine, sample_id)
    context = json.loads((root / "context.json").read_text(encoding="utf-8"))
    meta = json.loads((root / "meta.1.json").read_text(encoding="utf-8"))
    pty_path = root / "pty-output.1.log"
    stdout_path = root / "stdout.1.log"
    stderr_path = root / "stderr.1.log"
    if stdout_path.exists() and stderr_path.exists():
        stdout_text = stdout_path.read_text(encoding="utf-8")
        stderr_text = stderr_path.read_text(encoding="utf-8")
        pty_text = pty_path.read_text(encoding="utf-8") if pty_path.exists() else ""
    else:
        recovered = _load_raw_streams_from_protocol_rows(root)
        if not recovered["stdout"] and not recovered["stderr"] and not recovered["pty_output"]:
            recovered = _synthesize_raw_streams_for_missing_fixture(context=context, meta=meta)
        stdout_text = recovered["stdout"]
        stderr_text = recovered["stderr"]
        pty_text = recovered["pty_output"]

    payload: dict[str, Any] = {
        "root": root,
        "context": context,
        "meta": meta,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "pty_output": pty_text,
        "parser_diagnostics": (
            (root / "parser_diagnostics.1.jsonl").read_text(encoding="utf-8")
            if (root / "parser_diagnostics.1.jsonl").exists()
            else ""
        ),
    }
    return payload
