from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class RunStorePort(Protocol):
    def get_request(self, request_id: str) -> dict[str, Any] | None:
        ...

    def get_request_with_run(self, request_id: str) -> dict[str, Any] | None:
        ...

    def list_requests_with_runs(self, limit: int = 200) -> list[dict[str, Any]]:
        ...

    def get_pending_interaction(self, request_id: str) -> dict[str, Any] | None:
        ...

    def get_interaction_count(self, request_id: str) -> int:
        ...

    def list_interaction_history(self, request_id: str) -> list[dict[str, Any]]:
        ...

    def get_effective_session_timeout(self, request_id: str) -> int | None:
        ...


class WorkspacePort(Protocol):
    def get_run_dir(self, run_id: str) -> Path | None:
        ...


class JobBundlePort(Protocol):
    def _build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
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
