from __future__ import annotations

import json
import re
from typing import Any, cast

from server.runtime.auth_detection.types import AuthDetectionEvidence, EvidenceSource


class OpencodeAuthDetector:
    def build_evidence(
        self,
        *,
        engine: str,
        raw_stdout: str,
        raw_stderr: str,
        pty_output: str,
        runtime_parse_result: dict[str, Any] | None,
    ) -> AuthDetectionEvidence:
        extracted: dict[str, Any] = {
            "error_name": None,
            "status_code": None,
            "message": None,
            "provider_id": None,
            "response_error_type": None,
            "step_finish_unknown_count": 0,
            "saw_manual_interrupt": False,
        }
        diagnostics = []
        structured_types = []
        if isinstance(runtime_parse_result, dict):
            diagnostics = [str(item) for item in runtime_parse_result.get("diagnostics", []) if isinstance(item, str)]
            structured_types = [str(item) for item in runtime_parse_result.get("structured_types", []) if isinstance(item, str)]

        combined = "\n".join(part for part in [raw_stdout, raw_stderr, pty_output] if part)
        model_match = re.search(r"--model=([a-zA-Z0-9._-]+)/", combined)
        if model_match is not None:
            extracted["provider_id"] = model_match.group(1)
        structured_hits = 0
        for text in (raw_stdout, raw_stderr, pty_output):
            for line in text.splitlines():
                candidate = line.strip()
                if not candidate or not candidate.startswith("{"):
                    continue
                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if payload_type == "error":
                    error = payload.get("error")
                    if isinstance(error, dict):
                        extracted["error_name"] = error.get("name")
                        data = error.get("data")
                        if isinstance(data, dict):
                            extracted["status_code"] = data.get("statusCode")
                            extracted["message"] = data.get("message")
                            extracted["provider_id"] = data.get("providerID")
                            response_body = data.get("responseBody")
                            if isinstance(response_body, str):
                                try:
                                    response_payload = json.loads(response_body)
                                except json.JSONDecodeError:
                                    response_payload = None
                                if isinstance(response_payload, dict):
                                    error_payload = response_payload.get("error")
                                    if isinstance(error_payload, dict):
                                        extracted["response_error_type"] = error_payload.get("type")
                        structured_hits += 1
                elif payload_type == "step_finish":
                    part = payload.get("part")
                    if isinstance(part, dict) and part.get("reason") == "unknown":
                        extracted["step_finish_unknown_count"] = int(extracted["step_finish_unknown_count"]) + 1
                        structured_hits += 1

        if "^C" in combined or 'COMMAND_EXIT_CODE="130"' in combined:
            extracted["saw_manual_interrupt"] = True

        provider_id = extracted.get("provider_id")
        evidence_sources: list[EvidenceSource] = [
            "stdout_text",
            "stderr_text",
            "combined",
        ]
        if structured_hits:
            evidence_sources.append("structured_ndjson")

        return AuthDetectionEvidence(
            engine=engine,
            provider_id=provider_id if isinstance(provider_id, str) else None,
            stdout_text=raw_stdout,
            stderr_text=raw_stderr,
            pty_output=pty_output,
            combined_text=combined,
            parser_diagnostics=diagnostics,
            structured_types=cast(
                list[str],
                list(dict.fromkeys(str(item) for item in structured_types if isinstance(item, str))),
            ),
            extracted=extracted,
            evidence_sources=evidence_sources,
        )
