from __future__ import annotations

from pathlib import Path
from typing import cast

from server.runtime.observability.run_observability import (
    RunObservabilityService,
    configure_run_observability_ports,
)
from server.runtime.observability.run_read_facade import (
    RunReadFacade,
    configure_run_read_facade_ports,
)
from server.runtime.observability.run_source_adapter import (
    InstalledRunSourceAdapter,
    RunSourceAdapter,
    configure_run_source_ports,
    get_request_and_run_dir,
)
import server.runtime.observability.run_observability as observability_module
import server.runtime.observability.run_read_facade as read_facade_module
import server.runtime.observability.run_source_adapter as source_adapter_module


class _FakeRunStore:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def get_request(self, request_id: str):
        return {"request_id": request_id, "run_id": self._run_id, "runtime_options": {}, "engine": "codex"}


class _FakeWorkspace:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def get_run_dir(self, run_id: str):
        _ = run_id
        return self._run_dir


class _FakeJobControl:
    def _build_run_bundle(self, run_dir: Path, debug: bool = False):
        bundle_dir = run_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_dir / ("run_bundle_debug.zip" if debug else "run_bundle.zip")
        bundle_path.write_bytes(b"zip")
        return bundle_path.name

    async def cancel_run(self, **_kwargs):
        return True


def test_runtime_observability_ports_are_injected(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run-1"
    request_id = "req-1"

    fake_store = _FakeRunStore(run_id)
    fake_workspace = _FakeWorkspace(run_dir)

    previous_run_store = observability_module.run_store
    previous_workspace = observability_module.workspace_manager
    previous_parser_resolver = observability_module.parser_resolver
    previous_source_store = source_adapter_module.run_store
    previous_source_workspace = source_adapter_module.workspace_manager
    previous_job_control = read_facade_module.job_control

    try:
        configure_run_source_ports(run_store_backend=fake_store, workspace_backend=fake_workspace)
        configure_run_observability_ports(
            run_store_backend=fake_store,
            workspace_backend=fake_workspace,
            parser_resolver_backend=None,
        )
        configure_run_read_facade_ports(job_control_backend=_FakeJobControl())

        source_adapter = cast(RunSourceAdapter, InstalledRunSourceAdapter())
        request_record, resolved_run_dir = get_request_and_run_dir(source_adapter, request_id)
        assert request_record["run_id"] == run_id
        assert resolved_run_dir == run_dir

        assert RunObservabilityService()._run_store() is fake_store
        assert RunObservabilityService()._workspace() is fake_workspace
        assert RunReadFacade()._job_control().__class__.__name__ == "_FakeJobControl"
    finally:
        observability_module.run_store = previous_run_store
        observability_module.workspace_manager = previous_workspace
        observability_module.parser_resolver = previous_parser_resolver
        source_adapter_module.run_store = previous_source_store
        source_adapter_module.workspace_manager = previous_source_workspace
        read_facade_module.job_control = previous_job_control
