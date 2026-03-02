from __future__ import annotations

from pathlib import Path
from typing import Protocol

from server.models import RunStatus


class JobControlPort(Protocol):
    def build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
        ...

    async def cancel_run(
        self,
        *,
        run_id: str,
        engine_name: str,
        run_dir: Path,
        status: RunStatus,
        request_id: str | None = None,
        temp_request_id: str | None = None,
    ) -> bool:
        ...
