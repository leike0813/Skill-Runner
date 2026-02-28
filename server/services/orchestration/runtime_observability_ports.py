from __future__ import annotations

from server.runtime.observability.run_observability import configure_run_observability_ports
from server.runtime.observability.run_read_facade import configure_run_read_facade_ports
from server.runtime.observability.run_source_adapter import configure_run_source_ports
from server.services.orchestration.job_orchestrator import job_orchestrator
from server.services.orchestration.run_store import run_store
from server.services.orchestration.runtime_protocol_ports import runtime_parser_resolver
from server.services.orchestration.workspace_manager import workspace_manager


def install_runtime_observability_ports() -> None:
    configure_run_source_ports(
        run_store_backend=run_store,
        workspace_backend=workspace_manager,
    )
    configure_run_observability_ports(
        run_store_backend=run_store,
        workspace_backend=workspace_manager,
        parser_resolver_backend=runtime_parser_resolver,
    )
    configure_run_read_facade_ports(job_control_backend=job_orchestrator)
