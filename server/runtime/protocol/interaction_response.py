from __future__ import annotations

from typing import Any


def safe_interaction_response_preview(response: Any) -> str | None:
    """Return a display-safe preview without exposing managed file paths."""
    if isinstance(response, dict):
        if response.get("kind") == "interaction_files" and isinstance(response.get("files"), list):
            message = response.get("message")
            names = [
                str(item.get("name") or "").strip()
                for item in response["files"]
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            prefix = str(message).strip() if isinstance(message, str) else ""
            file_text = f"Uploaded files: {', '.join(names)}" if names else "Uploaded files"
            return f"{prefix} — {file_text}" if prefix else file_text
        text_obj = response.get("text")
        if isinstance(text_obj, str):
            normalized = text_obj.strip()
            return normalized or None
    if isinstance(response, str):
        normalized = response.strip()
        return normalized or None
    return None


__all__ = ["safe_interaction_response_preview"]
