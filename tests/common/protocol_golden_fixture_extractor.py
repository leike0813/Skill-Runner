from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, cast


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RUNS_PATH = PROJECT_ROOT / "tests" / "fixtures" / "protocol_golden" / "source_runs.json"
DATA_RUNS_ROOT = PROJECT_ROOT / "data" / "runs"

_OUTCOME_DATA_KEYS: dict[str, tuple[str, ...]] = {
    "demo-auto-skill": (
        "x",
        "y",
        "numbers",
        "comparison",
        "parity",
        "is_prime",
        "is_3x",
        "generated_at",
    ),
    "demo-interactive-skill": (
        "user_info",
        "user_worry",
        "advise",
    ),
    "literature-digest": (
        "digest_path",
        "references_path",
        "citation_analysis_path",
        "citation_analysis_report_path",
        "warnings",
        "error",
    ),
    "literature-explainer": (
        "note_path",
        "warnings",
        "error",
    ),
    "tag-regulator": (
        "input_tags",
        "remove_tags",
        "add_tags",
        "suggest_tags",
        "warnings",
        "error",
    ),
}

def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


@lru_cache(maxsize=1)
def load_protocol_golden_source_runs() -> dict[str, Any]:
    if not SOURCE_RUNS_PATH.exists():
        raise RuntimeError(f"Protocol golden source run registry not found: {SOURCE_RUNS_PATH}")
    payload = json.loads(SOURCE_RUNS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Protocol golden source run registry root must be a mapping")
    runs_obj = payload.get("runs")
    if not isinstance(runs_obj, list):
        raise RuntimeError("Protocol golden source run registry must declare `runs` as a list")
    return payload


def list_protocol_golden_source_runs() -> list[dict[str, Any]]:
    payload = load_protocol_golden_source_runs()
    return [dict(item) for item in payload["runs"] if isinstance(item, dict)]


def load_protocol_golden_source_run(source_run_key: str) -> dict[str, Any]:
    for item in list_protocol_golden_source_runs():
        if item.get("source_run_key") == source_run_key:
            return item
    raise RuntimeError(f"Unknown protocol golden source run `{source_run_key}`")


def _run_dir(source_run: Mapping[str, Any]) -> Path:
    run_id_obj = source_run.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj.strip():
        raise RuntimeError("Protocol golden source run missing `run_id`")
    run_dir = DATA_RUNS_ROOT / run_id_obj.strip()
    if not run_dir.exists():
        raise RuntimeError(f"Captured run not found for fixture source: {run_dir}")
    return run_dir


def _attempt_numbers(run_dir: Path) -> list[int]:
    numbers: list[int] = []
    for path in sorted((run_dir / ".audit").glob("meta.*.json")):
        suffix = path.stem.split(".")[-1]
        if suffix.isdigit():
            numbers.append(int(suffix))
    if not numbers:
        raise RuntimeError(f"No attempt meta files found for captured run: {run_dir}")
    return sorted(numbers)


def _pending_context_from_fcmp(fcmp_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in fcmp_events:
        if str(event.get("type") or "") != "user.input.required":
            continue
        data_obj = event.get("data")
        if not isinstance(data_obj, dict):
            continue
        payload: dict[str, Any] = {}
        interaction_id_obj = data_obj.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            payload["interaction_id"] = interaction_id_obj
        kind_obj = data_obj.get("kind")
        if isinstance(kind_obj, str) and kind_obj.strip():
            payload["kind"] = kind_obj.strip()
        prompt_obj = data_obj.get("prompt")
        if isinstance(prompt_obj, str) and prompt_obj.strip():
            payload["prompt"] = prompt_obj.strip()
        return payload or None
    return None


def _completion_payload(meta_payload: Mapping[str, Any]) -> dict[str, Any]:
    completion_obj = meta_payload.get("completion")
    return dict(completion_obj) if isinstance(completion_obj, dict) else {}


def _expected_rasp_for_attempt(
    *,
    status_hint: str,
    completion: Mapping[str, Any],
    pending_context: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    expected: list[dict[str, Any]] = [
        {"type": "lifecycle.run.status", "data": {"status": status_hint}},
    ]
    completion_payload: dict[str, Any] = {}
    for key in ("state", "reason_code", "source"):
        value = completion.get(key)
        if value is not None:
            completion_payload[key] = value
    if completion_payload:
        expected.append(
            {
                "type": "lifecycle.completion.state",
                "data": completion_payload,
            }
        )
    if status_hint == "waiting_user":
        user_input_payload: dict[str, Any] = {"kind": "free_text"}
        if pending_context is not None:
            interaction_id_obj = pending_context.get("interaction_id")
            if isinstance(interaction_id_obj, int):
                user_input_payload["interaction_id"] = interaction_id_obj
        expected.append(
            {
                "type": "interaction.user_input.required",
                "data": user_input_payload,
            }
        )
    return expected


def _expected_fcmp_for_attempt(
    *,
    attempt_number: int,
    status_hint: str,
    completion: Mapping[str, Any],
    pending_context: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    event: dict[str, Any] = {
        "type": "conversation.state.changed",
        "meta": {"attempt": attempt_number},
        "data": {},
    }
    if status_hint == "waiting_user":
        event["data"] = {
            "to": "waiting_user",
            "trigger": "turn.needs_input",
            "pending_owner": "waiting_user",
        }
    elif status_hint == "succeeded":
        event["data"] = {
            "to": "succeeded",
            "trigger": "turn.succeeded",
        }
        completion_source_obj = completion.get("source")
        if isinstance(completion_source_obj, str) and completion_source_obj:
            event["data"]["terminal"] = {"completion_source": completion_source_obj}
    elif status_hint == "failed":
        event["data"] = {
            "to": "failed",
            "trigger": "turn.failed",
        }
    else:
        event["data"] = {"to": status_hint}
    expected = [event]
    if status_hint == "waiting_user":
        user_input_payload: dict[str, Any] = {"kind": "free_text"}
        if pending_context is not None:
            interaction_id_obj = pending_context.get("interaction_id")
            if isinstance(interaction_id_obj, int):
                user_input_payload["interaction_id"] = interaction_id_obj
        expected.append(
            {
                "type": "user.input.required",
                "meta": {"attempt": attempt_number},
                "data": user_input_payload,
            }
        )
    return expected


def _expected_outcome_data(source_run: Mapping[str, Any], result_payload: Mapping[str, Any]) -> dict[str, Any]:
    category_obj = source_run.get("category")
    if not isinstance(category_obj, str) or category_obj not in _OUTCOME_DATA_KEYS:
        return {}
    data_obj = result_payload.get("data")
    if not isinstance(data_obj, Mapping):
        return {}
    allowed_keys = _OUTCOME_DATA_KEYS[category_obj]
    return {
        key: data_obj.get(key)
        for key in allowed_keys
        if key in data_obj
    }


def _protocol_fixture(
    *,
    fixture_id: str,
    source_run: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = _run_dir(source_run)
    audit_dir = run_dir / ".audit"
    attempts: list[dict[str, Any]] = []
    expected_rasp: list[dict[str, Any]] = []
    expected_fcmp: list[dict[str, Any]] = []
    attempt_statuses: list[str] = []
    for attempt_number in _attempt_numbers(run_dir):
        meta_path = audit_dir / f"meta.{attempt_number}.json"
        stdout_path = audit_dir / f"stdout.{attempt_number}.log"
        stderr_path = audit_dir / f"stderr.{attempt_number}.log"
        pty_path = audit_dir / f"pty-output.{attempt_number}.log"
        fcmp_path = audit_dir / f"fcmp_events.{attempt_number}.jsonl"
        if not meta_path.exists() or not stdout_path.exists() or not stderr_path.exists():
            raise RuntimeError(
                f"Captured run missing required attempt files for fixture `{fixture_id}`: attempt {attempt_number}"
            )
        meta_payload = _read_json(meta_path)
        completion_payload = _completion_payload(meta_payload)
        historical_fcmp = _read_jsonl(fcmp_path) if fcmp_path.exists() else []
        status_hint = str(meta_payload.get("status", "unknown"))
        attempt_statuses.append(status_hint)
        pending_context = _pending_context_from_fcmp(historical_fcmp)
        expected_rasp.extend(
            _expected_rasp_for_attempt(
                status_hint=status_hint,
                completion=completion_payload,
                pending_context=pending_context,
            )
        )
        expected_fcmp.extend(
            _expected_fcmp_for_attempt(
                attempt_number=attempt_number,
                status_hint=status_hint,
                completion=completion_payload,
                pending_context=pending_context,
            )
        )
        attempt_payload: dict[str, Any] = {
            "attempt_number": attempt_number,
            "status_hint": status_hint,
            "stdout": stdout_path.read_text(encoding="utf-8"),
            "stderr": stderr_path.read_text(encoding="utf-8"),
            "pty_output": pty_path.read_text(encoding="utf-8") if pty_path.exists() else "",
            "completion": completion_payload,
            "meta_file": _relative(meta_path),
        }
        if isinstance(pending_context, dict):
            attempt_payload["pending_context"] = pending_context
        attempts.append(attempt_payload)

    result_file = run_dir / "result" / "result.json"
    state_file = run_dir / ".state" / "state.json"
    meta_files = [_relative(audit_dir / f"meta.{n}.json") for n in _attempt_numbers(run_dir)]
    fcmp_files = [_relative(audit_dir / f"fcmp_events.{n}.jsonl") for n in _attempt_numbers(run_dir)]
    events_files = [_relative(audit_dir / f"events.{n}.jsonl") for n in _attempt_numbers(run_dir)]
    return {
        "fixture_id": fixture_id,
        "layer": "protocol_core",
        "engine": str(source_run["engine"]),
        "capture_mode": str(source_run["capture_mode"]),
        "capability_requirements": [],
        "inputs": {},
        "attempts": attempts,
        "run_artifacts": {
            "result_file": _relative(result_file),
            "state_file": _relative(state_file),
            "meta_files": meta_files,
            "fcmp_files": fcmp_files,
            "events_files": events_files,
        },
        "expected": {
            "rasp_events": expected_rasp,
            "fcmp_events": expected_fcmp,
            "protocol": {
                "attempt_count": len(attempts),
                "attempt_statuses": attempt_statuses,
            },
        },
        "normalization": {
            "ignore_fields": [
                "correlation.publish_id",
                "correlation.session_id",
                "correlation.thread_id",
                "raw_ref.byte_from",
                "raw_ref.byte_to",
            ]
        },
        "source": "captured_run",
        "source_run_id": str(source_run["run_id"]),
    }


def _outcome_fixture(
    *,
    fixture_id: str,
    source_run: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = _run_dir(source_run)
    audit_dir = run_dir / ".audit"
    attempt_numbers = _attempt_numbers(run_dir)
    last_attempt = attempt_numbers[-1]
    result_path = run_dir / "result" / "result.json"
    state_path = run_dir / ".state" / "state.json"
    meta_path = audit_dir / f"meta.{last_attempt}.json"
    if not result_path.exists() or not state_path.exists() or not meta_path.exists():
        raise RuntimeError(f"Captured run missing result/state/meta for fixture `{fixture_id}`")
    result_payload = _read_json(result_path)
    state_payload = _read_json(state_path)
    meta_payload = _read_json(meta_path)
    expected_data = _expected_outcome_data(source_run, result_payload)
    attempts = [
        {
            "attempt_number": number,
            "status_hint": str(_read_json(audit_dir / f"meta.{number}.json").get("status", "unknown")),
            "meta_file": _relative(audit_dir / f"meta.{number}.json"),
        }
        for number in attempt_numbers
    ]
    return {
        "fixture_id": fixture_id,
        "layer": "outcome_core",
        "engine": str(source_run["engine"]),
        "capture_mode": str(source_run["capture_mode"]),
        "capability_requirements": [],
        "inputs": {
            "result": result_payload,
            "state": state_payload,
            "meta": meta_payload,
        },
        "attempts": attempts,
        "run_artifacts": {
            "result_file": _relative(result_path),
            "state_file": _relative(state_path),
            "meta_files": [_relative(audit_dir / f"meta.{n}.json") for n in attempt_numbers],
        },
        "expected": {
            "outcome": {
                "final_status": str(state_payload.get("status", "")),
                "result_status": str(result_payload.get("status", "")),
                "success_source": result_payload.get("success_source"),
                "data": expected_data,
                "artifacts": list(result_payload.get("artifacts", []))
                if isinstance(result_payload.get("artifacts"), list)
                else [],
                "repair_level": result_payload.get("repair_level"),
                "validation_warnings": list(result_payload.get("validation_warnings", []))
                if isinstance(result_payload.get("validation_warnings"), list)
                else [],
                "error": result_payload.get("error"),
                "completion_reason_code": (
                    meta_payload.get("completion", {}).get("reason_code")
                    if isinstance(meta_payload.get("completion"), dict)
                    else None
                ),
                "completion_source": (
                    meta_payload.get("completion", {}).get("source")
                    if isinstance(meta_payload.get("completion"), dict)
                    else None
                ),
            }
        },
        "normalization": {
            "ignore_fields": [
                "request_id",
            ]
        },
        "source": "captured_run",
        "source_run_id": str(source_run["run_id"]),
    }


def build_protocol_golden_fixture_from_source_run(
    fixture_id: str,
    *,
    source_run_key: str,
    layer: str,
) -> dict[str, Any]:
    source_run = load_protocol_golden_source_run(source_run_key)
    if layer == "protocol_core":
        return _protocol_fixture(fixture_id=fixture_id, source_run=source_run)
    if layer == "outcome_core":
        return _outcome_fixture(fixture_id=fixture_id, source_run=source_run)
    raise RuntimeError(f"Unsupported captured-run fixture layer `{layer}`")
