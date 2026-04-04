from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.runtime.protocol.contracts import LiveStreamParserSession

if TYPE_CHECKING:
    from .execution_adapter import QwenExecutionAdapter


def _summarize(value: str, *, limit: int = 220) -> str:
    """Summarize text to a limited length."""
    compact = " ".join(value.replace("\r", "\n").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


class QwenStreamParser:
    """
    Stream parser for Qwen Code output.

    Parses NDJSON output from Qwen Code CLI:
    - user messages
    - assistant messages
    - result messages
    - stream_event messages (incremental updates)

    Phase 1: Basic parsing (user/assistant/result)
    Phase 2: Extended parsing (stream_event, tool_call, system)
    """

    def __init__(self, adapter: "QwenExecutionAdapter") -> None:
        self._adapter = adapter

    def parse(self, raw_stdout: str) -> dict[str, object]:
        """
        Parse raw stdout from Qwen Code CLI.

        Args:
            raw_stdout: Raw stdout string from CLI process

        Returns:
            Parsed result dictionary with turn_result
        """
        parsed_rows: list[dict[str, object]] = []

        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(event, dict):
                parsed_rows.append({"payload": event})

        last_message_text = ""
        session_id: str | None = None

        for row in parsed_rows:
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue

            event_type = payload.get("type")

            if event_type == "session_initialized":
                session_id = str(payload.get("session_id", ""))

            elif event_type == "assistant":
                message = payload.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if isinstance(text, str):
                                    last_message_text += text
                    elif isinstance(content, str):
                        last_message_text += content

            elif event_type == "result":
                if payload.get("subtype") == "success":
                    result_text = payload.get("result", "")
                    if isinstance(result_text, str) and result_text:
                        last_message_text = result_text

        if not last_message_text:
            last_message_text = raw_stdout

        result, repair_level = self._adapter._parse_json_with_deterministic_repair(
            last_message_text
        )  # noqa: SLF001

        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(
                result, repair_level
            )  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001

            turn_result_dict = turn_result.model_dump()
            if session_id:
                turn_result_dict["session_handle"] = {
                    "handle_type": "session_id",
                    "handle_value": session_id,
                }

            return {
                "turn_result": turn_result_dict,
                "structured_payload": structured_payload,
            }

        turn_result = self._adapter._turn_error(message="failed to parse qwen output")  # noqa: SLF001
        return {
            "turn_result": turn_result.model_dump(),
            "structured_payload": None,
        }

    def start_live_session(self) -> LiveStreamParserSession:
        raise NotImplementedError("Qwen live stream parser is not implemented yet")
