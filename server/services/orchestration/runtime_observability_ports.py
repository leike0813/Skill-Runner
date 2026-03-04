from __future__ import annotations

from server.runtime.observability.job_control_port import JobControlPort
from server.runtime.observability.run_observability import configure_run_observability_ports
from server.runtime.observability.run_read_facade import configure_run_read_facade_ports
from server.runtime.observability.run_source_adapter import configure_run_source_ports
from server.services.orchestration.job_orchestrator import job_orchestrator
from server.services.orchestration.run_auth_orchestration_service import run_auth_orchestration_service
from server.services.orchestration.run_recovery_service import run_recovery_service
from server.services.orchestration.run_store import run_store
from server.services.orchestration.runtime_protocol_ports import runtime_parser_resolver
from server.services.orchestration.workspace_manager import workspace_manager


def install_runtime_observability_ports() -> None:
    async def _queued_resume_redriver(
        *,
        request_id: str,
        run_id: str,
        engine_name: str,
        run_store_backend: object,
    ) -> bool:
        return await run_recovery_service.redrive_resume_ticket_if_needed(
            request_id=request_id,
            run_id=run_id,
            engine_name=engine_name,
            run_store_backend=run_store_backend,
            resume_run_job=job_orchestrator.run_job,
            recovery_reason="resume_ticket_redriven_online",
        )

    configure_run_source_ports(
        run_store_backend=run_store,
        workspace_backend=workspace_manager,
    )
    configure_run_observability_ports(
        run_store_backend=run_store,
        workspace_backend=workspace_manager,
        parser_resolver_backend=runtime_parser_resolver,
        waiting_auth_reconciler_backend=run_auth_orchestration_service.reconcile_waiting_auth,
        queued_resume_redriver_backend=_queued_resume_redriver,
    )
    job_control: JobControlPort = job_orchestrator
    configure_run_read_facade_ports(job_control_backend=job_control)
