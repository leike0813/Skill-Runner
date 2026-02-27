from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class DriverKey:
    transport: str
    engine: str
    auth_method: str
    provider_id: Optional[str] = None


class AuthDriverRegistry:
    """Registry for transport-specific auth driver capabilities."""

    def __init__(self) -> None:
        self._drivers: Dict[DriverKey, Any] = {}

    def register(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: Optional[str] = None,
        driver: Any = True,
    ) -> None:
        key = DriverKey(
            transport=transport.strip().lower(),
            engine=engine.strip().lower(),
            auth_method=auth_method.strip().lower(),
            provider_id=(provider_id.strip().lower() if isinstance(provider_id, str) and provider_id.strip() else None),
        )
        self._drivers[key] = driver

    def resolve(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: Optional[str] = None,
    ) -> Tuple[DriverKey, Any]:
        normalized = DriverKey(
            transport=transport.strip().lower(),
            engine=engine.strip().lower(),
            auth_method=auth_method.strip().lower(),
            provider_id=(provider_id.strip().lower() if isinstance(provider_id, str) and provider_id.strip() else None),
        )
        driver = self._drivers.get(normalized)
        if driver is not None:
            return normalized, driver
        fallback = DriverKey(
            transport=normalized.transport,
            engine=normalized.engine,
            auth_method=normalized.auth_method,
            provider_id=None,
        )
        driver = self._drivers.get(fallback)
        if driver is None:
            raise KeyError(
                f"Unsupported auth driver combination: transport={normalized.transport}, "
                f"engine={normalized.engine}, auth_method={normalized.auth_method}, "
                f"provider_id={normalized.provider_id or '-'}"
            )
        return normalized, driver

    def supports(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: Optional[str] = None,
    ) -> bool:
        try:
            self.resolve(
                transport=transport,
                engine=engine,
                auth_method=auth_method,
                provider_id=provider_id,
            )
            return True
        except KeyError:
            return False
