from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from server.models import InteractiveErrorCode, OrchestratorEventType, RunStatus
from server.runtime.protocol.factories import (
    make_diagnostic_warning_payload,
    make_orchestrator_event,
)
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_orchestrator_event,
)

from .run_filesystem_snapshot_service import RunFilesystemSnapshotService

DONE_MARKER_STREAM_PATTERN = re.compile(
    r'(?:\\)?"__SKILL_DONE__(?:\\)?"\s*:\s*true',
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


class RunAuditService:
    def __init__(self, snapshot_service: RunFilesystemSnapshotService | None = None):
        self.snapshot_service = snapshot_service or RunFilesystemSnapshotService()

    def find_done_markers(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
        turn_payload: dict[str, Any],
    ) -> dict[str, Any]:
        done_signal_found = "__SKILL_DONE__" in turn_payload and turn_payload.get("__SKILL_DONE__") is True
        markers: list[dict[str, Any]] = []
        if adapter is not None:
            try:
                parsed = adapter.parse_runtime_stream(
                    stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                    stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                    pty_raw=b"",
                )
            except Exception as exc:
                # Third-party adapter boundary: preserve non-blocking fallback to avoid
                # affecting completion classification when parser behavior is unknown.
                logger.warning(
                    "failed to parse runtime stream for done-marker scan",
                    extra={
                        "component": "orchestration.run_audit_service",
                        "action": "find_done_markers.parse_runtime_stream",
                        "error_type": type(exc).__name__,
                        "fallback": "skip_done_marker_scan_for_stream",
                    },
                    exc_info=True,
                )
                parsed = None

            assistant_messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
            if isinstance(assistant_messages, list):
                for item in assistant_messages:
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if not isinstance(text_obj, str) or not text_obj:
                        continue
                    raw_ref_obj = item.get("raw_ref")
                    raw_ref = raw_ref_obj if isinstance(raw_ref_obj, dict) else {}
                    marker_stream_obj = raw_ref.get("stream")
                    marker_stream = (
                        marker_stream_obj
                        if isinstance(marker_stream_obj, str) and marker_stream_obj
                        else "assistant"
                    )
                    marker_byte_from = raw_ref.get("byte_from")
                    marker_byte_to = raw_ref.get("byte_to")
                    for _match in DONE_MARKER_STREAM_PATTERN.finditer(text_obj):
                        markers.append(
                            {
                                "stream": marker_stream,
                                "byte_from": marker_byte_from,
                                "byte_to": marker_byte_to,
                            }
                        )
        return {
            "done_signal_found": done_signal_found,
            "done_marker_found": bool(markers),
            "done_marker_count": len(markers),
            "first_marker": markers[0] if markers else None,
        }

    def contains_done_marker_in_stream(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
    ) -> bool:
        done_info = self.find_done_markers(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            turn_payload={},
        )
        return bool(done_info.get("done_marker_found"))

    def classify_completion(
        self,
        *,
        status: RunStatus | None,
        process_exit_code: int | None,
        done_info: dict[str, Any],
        validation_warnings: list[str],
        terminal_error_code: str | None,
    ) -> dict[str, Any]:
        done_signal_found = bool(done_info.get("done_signal_found"))
        done_marker_found = bool(done_info.get("done_marker_found"))
        marker_count = int(done_info.get("done_marker_count") or 0)
        diagnostics: list[str] = []
        if marker_count > 1:
            diagnostics.append("MULTIPLE_DONE_MARKERS_IGNORED")

        if done_signal_found:
            return {
                "state": "completed",
                "reason_code": "DONE_SIGNAL_FOUND",
                "diagnostics": diagnostics,
            }
        if process_exit_code is not None and int(process_exit_code) != 0:
            if done_marker_found:
                diagnostics.append("DONE_MARKER_PROCESS_FAILURE_CONFLICT")
            return {
                "state": "interrupted",
                "reason_code": "PROCESS_EXIT_NONZERO",
                "diagnostics": diagnostics,
            }
        if terminal_error_code == InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value:
            diagnostics.append(InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value)
            return {
                "state": "interrupted",
                "reason_code": InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value,
                "diagnostics": diagnostics,
            }
        if status == RunStatus.SUCCEEDED:
            if "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in validation_warnings:
                diagnostics.append("DONE_MARKER_MISSING")
                diagnostics.append("INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER")
                return {
                    "state": "completed",
                    "reason_code": "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER",
                    "diagnostics": diagnostics,
                }
            if done_marker_found:
                return {
                    "state": "completed",
                    "reason_code": "DONE_MARKER_FOUND",
                    "diagnostics": diagnostics,
                }
            return {
                "state": "completed",
                "reason_code": "OUTPUT_VALIDATED",
                "diagnostics": diagnostics,
            }
        if done_marker_found:
            return {
                "state": "completed",
                "reason_code": "DONE_MARKER_FOUND",
                "diagnostics": diagnostics,
            }
        if status == RunStatus.WAITING_USER:
            diagnostics.append("DONE_MARKER_MISSING")
            return {
                "state": "awaiting_user_input",
                "reason_code": "WAITING_USER_INPUT",
                "diagnostics": diagnostics,
            }
        if status == RunStatus.WAITING_AUTH:
            diagnostics.append("DONE_MARKER_MISSING")
            return {
                "state": "awaiting_auth",
                "reason_code": "WAITING_AUTH_REQUIRED",
                "diagnostics": diagnostics,
            }
        if status in {RunStatus.FAILED, RunStatus.CANCELED}:
            return {
                "state": "interrupted",
                "reason_code": terminal_error_code or "TERMINAL_SIGNAL_FAILED",
                "diagnostics": diagnostics,
            }
        return {
            "state": "unknown",
            "reason_code": "INSUFFICIENT_EVIDENCE",
            "diagnostics": diagnostics,
        }

    def write_attempt_audit_artifacts(
        self,
        *,
        run_dir: Path,
        run_id: str,
        request_id: str | None,
        engine_name: str,
        execution_mode: str,
        attempt_number: int,
        started_at: datetime,
        finished_at: datetime,
        status: RunStatus | None,
        fs_before_snapshot: dict[str, dict[str, Any]],
        process_exit_code: int | None,
        process_failure_reason: str | None,
        process_raw_stdout: str,
        process_raw_stderr: str,
        adapter: Any | None,
        turn_payload: dict[str, Any],
        validation_warnings: list[str],
        terminal_error_code: str | None,
        options: dict[str, Any],
        auth_detection: dict[str, Any] | None = None,
        auth_session: dict[str, Any] | None = None,
    ) -> None:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{attempt_number}"
        meta_path = audit_dir / f"meta{suffix}.json"
        stdin_path = audit_dir / f"stdin{suffix}.log"
        stdout_path = audit_dir / f"stdout{suffix}.log"
        stderr_path = audit_dir / f"stderr{suffix}.log"
        pty_output_path = audit_dir / f"pty-output{suffix}.log"
        fs_before_path = audit_dir / f"fs-before{suffix}.json"
        fs_after_path = audit_dir / f"fs-after{suffix}.json"
        fs_diff_path = audit_dir / f"fs-diff{suffix}.json"
        parser_diagnostics_path = audit_dir / f"parser_diagnostics{suffix}.jsonl"
        stdout_text = process_raw_stdout
        stderr_text = process_raw_stderr
        pty_text = f"{stdout_text}{stderr_text}"
        stdin_payload = options.get("__interactive_reply_payload")
        if stdin_payload is None:
            stdin_text = ""
        else:
            stdin_text = json.dumps(stdin_payload, ensure_ascii=False)

        stdin_path.write_text(stdin_text, encoding="utf-8")
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        pty_output_path.write_text(pty_text, encoding="utf-8")

        fs_after_snapshot = self.snapshot_service.capture_filesystem_snapshot(run_dir)
        fs_diff = self.snapshot_service.diff_filesystem_snapshot(fs_before_snapshot, fs_after_snapshot)
        fs_before_path.write_text(
            json.dumps(fs_before_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fs_after_path.write_text(
            json.dumps(fs_after_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fs_diff_path.write_text(
            json.dumps(fs_diff, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        done_info = self.find_done_markers(
            adapter=adapter,
            raw_stdout=stdout_text,
            raw_stderr=stderr_text,
            turn_payload=turn_payload,
        )
        completion = self.classify_completion(
            status=status,
            process_exit_code=process_exit_code,
            done_info=done_info,
            validation_warnings=validation_warnings,
            terminal_error_code=terminal_error_code,
        )

        reconstruction_error = None
        stdout_chunks = len(str(stdout_text).splitlines())
        stderr_chunks = len(str(stderr_text).splitlines())

        status_text = status.value if isinstance(status, RunStatus) else (str(status) if status else "unknown")
        meta_payload = {
            "run_id": run_id,
            "request_id": request_id,
            "engine": engine_name,
            "execution_mode": execution_mode,
            "attempt": {"number": attempt_number},
            "status": status_text,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "process": {
                "exit_code": process_exit_code,
                "failure_reason": process_failure_reason,
            },
            "completion": {
                **completion,
                "done_signal_found": bool(done_info.get("done_signal_found")),
                "done_marker_found": bool(done_info.get("done_marker_found")),
                "done_marker_count": int(done_info.get("done_marker_count") or 0),
                "first_done_marker": done_info.get("first_marker"),
            },
            "validation_warnings": [str(item) for item in validation_warnings],
            "reconstruction_used": False,
            "stdout_chunks": stdout_chunks,
            "stderr_chunks": stderr_chunks,
            "reconstruction_error": reconstruction_error,
            "filesystem_diff": fs_diff,
            "auth_detection": auth_detection
            or {
                "classification": "unknown",
                "subcategory": None,
                "confidence": "low",
                "engine": engine_name,
                "provider_id": None,
                "matched_rule_ids": [],
                "evidence_sources": [],
                "evidence_excerpt": None,
                "details": {},
            },
            "auth_session": auth_session
            or {
                "session_id": None,
                "engine": engine_name,
                "provider_id": None,
                "challenge_kind": None,
                "status": "none",
                "source_attempt": attempt_number,
                "resume_attempt": None,
                "last_error": None,
                "redacted_submission": {"kind": None, "present": False},
            },
        }
        meta_path.write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_auth_detection_diagnostic(
            path=parser_diagnostics_path,
            run_id=run_id,
            attempt_number=attempt_number,
            engine_name=engine_name,
            auth_detection=auth_detection,
        )

    def _write_auth_detection_diagnostic(
        self,
        *,
        path: Path,
        run_id: str,
        attempt_number: int,
        engine_name: str,
        auth_detection: dict[str, Any] | None,
    ) -> None:
        if not isinstance(auth_detection, dict):
            return
        confidence = auth_detection.get("confidence")
        classification = auth_detection.get("classification")
        if classification != "auth_required" or confidence not in {"high", "low"}:
            return
        seq = self._next_jsonl_seq(path)
        confidence_score = 1.0 if confidence == "high" else 0.3
        matched_rule_ids = auth_detection.get("matched_rule_ids", [])
        matched_pattern_id = None
        if isinstance(matched_rule_ids, list) and matched_rule_ids:
            first = matched_rule_ids[0]
            if isinstance(first, str) and first.strip():
                matched_pattern_id = first.strip()
        details_obj = auth_detection.get("details")
        reason_code = (
            details_obj.get("reason_code")
            if isinstance(details_obj, dict) and isinstance(details_obj.get("reason_code"), str)
            else None
        )
        provider_id = auth_detection.get("provider_id")
        provider_id_value = provider_id if isinstance(provider_id, str) and provider_id else None
        code = "AUTH_SIGNAL_MATCHED_HIGH" if confidence == "high" else "AUTH_SIGNAL_MATCHED_LOW"
        payload = {
            "protocol_version": "rasp/1.0",
            "run_id": run_id,
            "seq": seq,
            "ts": datetime.utcnow().isoformat(),
            "source": {
                "engine": engine_name,
                "parser": "auth_signal",
                "confidence": confidence_score,
            },
            "event": {
                "category": "diagnostic",
                "type": "diagnostic.warning",
            },
            "data": {
                "code": code,
                "auth_signal": {
                    "matched_pattern_id": matched_pattern_id,
                    "confidence": confidence,
                    "provider_id": provider_id_value,
                    "reason_code": reason_code,
                },
            },
            "correlation": {},
            "attempt_number": attempt_number,
            "raw_ref": None,
        }
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False))
            fp.write("\n")

    def _next_jsonl_seq(self, path: Path) -> int:
        if not path.exists() or not path.is_file():
            return 1
        seq = 0
        try:
            with path.open("r", encoding="utf-8") as fp:
                for seq, _line in enumerate(fp, start=1):
                    continue
        except OSError:
            return 1
        return seq + 1

    def append_orchestrator_event(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        category: str,
        type_name: str,
        data: dict[str, Any],
    ) -> None:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        event_path = audit_dir / f"orchestrator_events.{attempt_number}.jsonl"
        event_seq = self.next_orchestrator_event_seq(event_path)
        payload = make_orchestrator_event(
            attempt_number=attempt_number,
            seq=event_seq,
            category=category,
            type_name=type_name,
            data=data,
            ts=datetime.utcnow().isoformat(),
        )
        try:
            validate_orchestrator_event(payload)
        except ProtocolSchemaViolation as exc:
            raise RuntimeError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value} [{type_name}]: {exc}"
            ) from exc
        with event_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False))
            fp.write("\n")

    def next_orchestrator_event_seq(self, event_path: Path) -> int:
        if not event_path.exists() or not event_path.is_file():
            return 1
        max_seq = 0
        fallback_count = 0
        try:
            with event_path.open("r", encoding="utf-8") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    fallback_count += 1
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    seq_obj = payload.get("seq")
                    if isinstance(seq_obj, int) and seq_obj > max_seq:
                        max_seq = seq_obj
        except OSError:
            return max(1, fallback_count + 1)
        if max_seq > 0:
            return max_seq + 1
        return max(1, fallback_count + 1)

    def append_internal_schema_warning(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        schema_path: str,
        detail: str,
    ) -> None:
        self.append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="diagnostic",
            type_name=OrchestratorEventType.DIAGNOSTIC_WARNING.value,
            data=make_diagnostic_warning_payload(
                code="SCHEMA_INTERNAL_INVALID",
                path=schema_path,
                detail=detail,
            ),
        )
