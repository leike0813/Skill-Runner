from __future__ import annotations

from typing import Any, Protocol


class OAuthProxyDriver(Protocol):
    def start(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def refresh(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def cancel(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def input(self, **kwargs: Any) -> dict[str, Any]:
        ...


class CliDelegateDriver(Protocol):
    def start(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def refresh(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def cancel(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def input(self, **kwargs: Any) -> dict[str, Any]:
        ...
