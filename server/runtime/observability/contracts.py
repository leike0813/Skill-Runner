from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol


class RunStorePort(Protocol):
    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        ...

    async def get_request_with_run(self, request_id: str) -> dict[str, Any] | None:
        ...

    async def list_requests_with_runs(self, limit: int = 200) -> list[dict[str, Any]]:
        ...

    async def get_pending_interaction(self, request_id: str) -> dict[str, Any] | None:
        ...

    async def get_pending_auth(self, request_id: str) -> dict[str, Any] | None:
        ...

    async def get_pending_auth_method_selection(self, request_id: str) -> dict[str, Any] | None:
        ...

    async def get_interaction_count(self, request_id: str) -> int:
        ...

    async def list_interaction_history(self, request_id: str) -> list[dict[str, Any]]:
        ...

    async def get_effective_session_timeout(self, request_id: str) -> int | None:
        ...


class WorkspacePort(Protocol):
    def get_run_dir(self, run_id: str) -> Path | None:
        ...


WaitingAuthReconciler = Callable[..., Awaitable[bool]]
QueuedResumeRedriver = Callable[..., Awaitable[bool]]


class JobBundlePort(Protocol):
    def build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
        ...

    async def cancel_run(
        self,
        *,
        run_id: str,
        engine_name: str,
        run_dir: Path,
        status: Any,
        request_id: str | None = None,
        temp_request_id: str | None = None,
    ) -> bool:
        ...
