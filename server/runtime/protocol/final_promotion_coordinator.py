from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from server.runtime.adapter.types import RuntimeStreamRawRef


@dataclass(frozen=True)
class PromotableMessage:
    message_id: str
    message_family_id: str
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


def resolve_message_id(
    *,
    message_id: str | None,
    text: str,
    attempt_number: int,
    raw_ref: RuntimeStreamRawRef | None = None,
) -> str:
    normalized = message_id.strip() if isinstance(message_id, str) else ""
    if normalized:
        return normalized

    stream = ""
    byte_from = -1
    byte_to = -1
    if isinstance(raw_ref, dict):
        stream = str(raw_ref.get("stream") or "").strip().lower()
        byte_from = int(raw_ref.get("byte_from") or -1)
        byte_to = int(raw_ref.get("byte_to") or -1)
    fingerprint = "\n".join(
        [
            str(max(1, int(attempt_number))),
            stream,
            str(byte_from),
            str(byte_to),
            text.strip(),
        ]
    )
    digest = hashlib.sha1(fingerprint.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"m_{attempt_number}_{digest}"


def build_process_payload(
    *,
    message_id: str,
    summary: str,
    classification: str,
    details: Dict[str, Any] | None = None,
    text: str | None = None,
    replaces_message_id: str | None = None,
    message_family_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message_id": message_id,
        "summary": summary,
        "classification": classification,
        "details": details or {},
    }
    family_id = message_family_id.strip() if isinstance(message_family_id, str) else ""
    payload["message_family_id"] = family_id or message_id
    if isinstance(text, str) and text.strip():
        payload["text"] = text
    if isinstance(replaces_message_id, str) and replaces_message_id.strip():
        payload["replaces_message_id"] = replaces_message_id.strip()
    return payload


class FinalPromotionCoordinator:
    """Generic, engine-agnostic process-message promotion coordinator."""

    def __init__(self, *, message_family_id: str | None = None) -> None:
        self._latest_candidate: PromotableMessage | None = None
        self._promoted_ids: set[str] = set()
        normalized_family = message_family_id.strip() if isinstance(message_family_id, str) else ""
        self._message_family_id = normalized_family or None

    def register_message_candidate(
        self,
        *,
        message_id: str,
        message_family_id: str | None = None,
        text: str,
        raw_ref: RuntimeStreamRawRef | None = None,
        details: Dict[str, Any] | None = None,
    ) -> PromotableMessage:
        family_id = message_family_id.strip() if isinstance(message_family_id, str) else ""
        if not family_id:
            family_id = self._message_family_id or message_id
        candidate = PromotableMessage(
            message_id=message_id,
            message_family_id=family_id,
            text=text,
            summary=build_summary(text),
            details=dict(details or {}),
            classification="intermediate",
            raw_ref=raw_ref,
        )
        self._latest_candidate = candidate
        return candidate

    def register_reasoning_candidate(
        self,
        *,
        message_id: str,
        message_family_id: str | None = None,
        text: str,
        raw_ref: RuntimeStreamRawRef | None = None,
        details: Dict[str, Any] | None = None,
    ) -> PromotableMessage:
        return self.register_message_candidate(
            message_id=message_id,
            message_family_id=message_family_id,
            text=text,
            raw_ref=raw_ref,
            details=details,
        )

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
            message_family_id=candidate.message_family_id,
            summary=candidate.summary,
            classification="promoted",
            details={"from": candidate.classification, "to": "final"},
            text=candidate.text,
            replaces_message_id=candidate.message_id,
        )

    @staticmethod
    def final_payload(candidate: PromotableMessage) -> dict[str, Any]:
        return build_process_payload(
            message_id=candidate.message_id,
            message_family_id=candidate.message_family_id,
            summary=candidate.summary,
            classification="final",
            details=candidate.details,
            text=candidate.text,
            replaces_message_id=candidate.message_id,
        )
