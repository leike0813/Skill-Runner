from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from server.runtime.adapter.types import RuntimeStreamRawRef


@dataclass(frozen=True)
class PromotableMessage:
    message_id: str
    text: str
    summary: str
    details: Dict[str, Any]
    classification: str
    raw_ref: RuntimeStreamRawRef | None


def build_summary(text: str, *, max_chars: int = 220) -> str:
    compact = " ".join(text.replace("\r", "\n").split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def build_process_payload(
    *,
    message_id: str,
    summary: str,
    classification: str,
    details: Dict[str, Any] | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message_id": message_id,
        "summary": summary,
        "classification": classification,
        "details": details or {},
    }
    if isinstance(text, str) and text.strip():
        payload["text"] = text
    return payload


class FinalPromotionCoordinator:
    """Generic, engine-agnostic process-message promotion coordinator."""

    def __init__(self) -> None:
        self._latest_candidate: PromotableMessage | None = None
        self._promoted_ids: set[str] = set()

    def register_reasoning_candidate(
        self,
        *,
        message_id: str,
        text: str,
        raw_ref: RuntimeStreamRawRef | None = None,
        details: Dict[str, Any] | None = None,
    ) -> PromotableMessage:
        candidate = PromotableMessage(
            message_id=message_id,
            text=text,
            summary=build_summary(text),
            details=dict(details or {}),
            classification="reasoning",
            raw_ref=raw_ref,
        )
        self._latest_candidate = candidate
        return candidate

    def promote_on_turn_end(self) -> PromotableMessage | None:
        return self._promote_latest()

    def fallback_promote_for_status(self, status: str | None) -> PromotableMessage | None:
        if status not in {"succeeded", "waiting_user"}:
            return None
        return self._promote_latest()

    def _promote_latest(self) -> PromotableMessage | None:
        candidate = self._latest_candidate
        if candidate is None:
            return None
        if candidate.message_id in self._promoted_ids:
            return None
        self._promoted_ids.add(candidate.message_id)
        return candidate

    def was_promoted(self, message_id: str) -> bool:
        return message_id in self._promoted_ids

    @staticmethod
    def promoted_payload(candidate: PromotableMessage) -> dict[str, Any]:
        return build_process_payload(
            message_id=candidate.message_id,
            summary=candidate.summary,
            classification="promoted",
            details={"from": "reasoning", "to": "final"},
            text=candidate.text,
        )

    @staticmethod
    def final_payload(candidate: PromotableMessage) -> dict[str, Any]:
        return build_process_payload(
            message_id=candidate.message_id,
            summary=candidate.summary,
            classification="final",
            details=candidate.details,
            text=candidate.text,
        )
