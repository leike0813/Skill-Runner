from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class AuthDriverContext:
    transport: str
    engine: str
    auth_method: str
    provider_id: Optional[str] = None
    method: str = "auth"
    callback_base_url: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthDriverResult:
    status: str
    auth_ready: bool
    auth_url: Optional[str] = None
    user_code: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    input_kind: Optional[str] = None
    audit: Optional[dict[str, Any]] = None
