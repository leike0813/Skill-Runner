from __future__ import annotations

from pathlib import Path
from typing import Any

from server.runtime.workspace_layout import RunWorkspaceLayout


DEFAULT_NAMESPACE = "demo.1"


def make_layout(
    workspace: Path,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    workspace_id: str | None = None,
) -> RunWorkspaceLayout:
    return RunWorkspaceLayout(
        workspace_id=workspace_id or workspace.name,
        workspace_dir=workspace,
        namespace=namespace,
    )


def layout_record(
    *,
    request_id: str = "req-1",
    run_id: str = "run-1",
    workspace: Path,
    namespace: str = DEFAULT_NAMESPACE,
    status: str = "running",
    engine: str = "codex",
    skill_id: str = "demo",
    runtime_options: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    layout = make_layout(workspace, namespace=namespace)
    return {
        "request_id": request_id,
        "run_id": run_id,
        "skill_id": skill_id,
        "engine": engine,
        "runtime_options": runtime_options or {"execution_mode": "interactive"},
        "effective_runtime_options": runtime_options or {"execution_mode": "interactive"},
        "run_status": status,
        "status": status,
        "workspace_id": layout.workspace_id,
        "workspace_dir": str(layout.workspace_dir),
        "workspace_namespace": layout.namespace,
        "result_path": str(layout.result_path),
        "input_manifest_path": str(layout.input_manifest_path),
        "run_input_manifest_path": str(layout.input_manifest_path),
        **extra,
    }


def state_payload(
    *,
    request_id: str = "req-1",
    run_id: str = "run-1",
    status: str = "running",
    current_attempt: int = 1,
    pending_interaction_id: int | None = None,
    pending_owner: str | None = None,
    error: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "run_id": run_id,
        "status": status,
        "updated_at": "2026-01-01T00:00:00",
        "current_attempt": current_attempt,
        "pending_interaction_id": pending_interaction_id,
        "pending_owner": pending_owner,
        "pending": {
            "owner": pending_owner,
            "interaction_id": pending_interaction_id,
            "auth_session_id": None,
            "payload": None,
        },
        "resume": {
            "resume_ticket_id": None,
            "resume_cause": None,
            "source_attempt": None,
            "target_attempt": None,
        },
        "state_phase": {"waiting_auth_phase": None, "dispatch_phase": None},
        "runtime": {},
        "error": error,
        "warnings": [],
        **extra,
    }


def adapter_options(
    layout: RunWorkspaceLayout,
    *,
    run_id: str = "run-1",
    request_id: str = "req-1",
    attempt: int = 1,
    engine: str = "codex",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "__run_id": run_id,
        "__request_id": request_id,
        "__attempt_number": attempt,
        "__engine_name": engine,
        "__audit_dir": str(layout.audit_dir),
        "__input_manifest_path": str(layout.input_manifest_path),
        "__result_json_path": str(layout.result_path),
        **extra,
    }


async def seed_request_bound_store(
    store: Any,
    *,
    request_id: str = "req-1",
    run_id: str = "run-1",
    workspace: Path,
    namespace: str = DEFAULT_NAMESPACE,
    status: str = "running",
    engine: str = "codex",
    skill_id: str = "demo",
    runtime_options: dict[str, Any] | None = None,
) -> RunWorkspaceLayout:
    layout = make_layout(workspace, namespace=namespace)
    await store.create_request(
        request_id=request_id,
        skill_id=skill_id,
        engine=engine,
        input_data={},
        parameter={},
        engine_options={},
        runtime_options=runtime_options or {"execution_mode": "interactive"},
    )
    await store.create_run(
        run_id=run_id,
        cache_key=None,
        status=status,
        result_path=str(layout.result_path),
        workspace_id=layout.workspace_id,
        workspace_dir=str(layout.workspace_dir),
        workspace_namespace=layout.namespace,
        input_manifest_path=str(layout.input_manifest_path),
    )
    await store.update_request_run_id(request_id, run_id)
    return layout
