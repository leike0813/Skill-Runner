from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]

from ..models import (
    AuthSessionCancelResponseV2,
    AuthSessionInputRequestV2,
    AuthSessionInputResponseV2,
    AuthSessionSnapshotV2,
    AuthSessionStartRequestV2,
    EngineAuthSessionCancelResponse,
    EngineAuthSessionInputRequest,
    EngineAuthSessionInputResponse,
    EngineAuthSessionSnapshot,
    EngineAuthSessionStartRequest,
    EngineAuthStatusResponse,
    EngineManifestModelInfo,
    EngineManifestViewResponse,
    EngineModelInfo,
    EngineModelsResponse,
    EngineSnapshotCreateRequest,
    EngineUpgradeCreateRequest,
    EngineUpgradeCreateResponse,
    EngineUpgradeEngineResult,
    EngineUpgradeStatusResponse,
    EngineUpgradeTaskStatus,
    EnginesResponse,
)
from ..runtime.auth.orchestrators.cli_delegate import CliDelegateOrchestrator
from ..runtime.auth.orchestrators.oauth_proxy import OAuthProxyOrchestrator
from ..runtime.auth.callbacks import oauth_callback_router
from ..services.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeValidationError,
    engine_upgrade_manager,
)
from ..services.engine_auth_flow_manager import engine_auth_flow_manager
from ..services.engine_interaction_gate import EngineInteractionBusyError
from ..services.model_registry import model_registry
from ..services.agent_cli_manager import AgentCliManager
from ..services.ui_auth import require_ui_basic_auth

router = APIRouter(prefix="/engines", tags=["engines"])
agent_cli_manager = AgentCliManager()
oauth_proxy_orchestrator = OAuthProxyOrchestrator(engine_auth_flow_manager)
cli_delegate_orchestrator = CliDelegateOrchestrator(engine_auth_flow_manager)


@router.get("", response_model=EnginesResponse)
async def list_engines():
    return EnginesResponse(engines=model_registry.list_engines())


@router.get("/{engine}/models", response_model=EngineModelsResponse)
async def list_models(engine: str):
    try:
        catalog = model_registry.get_models(engine)
        return EngineModelsResponse(
            engine=catalog.engine,
            cli_version_detected=catalog.cli_version_detected,
            snapshot_version_used=catalog.snapshot_version_used,
            source=catalog.source,
            fallback_reason=catalog.fallback_reason,
            models=[
                EngineModelInfo(
                    id=entry.id,
                    display_name=entry.display_name,
                    deprecated=entry.deprecated,
                    notes=entry.notes,
                    supported_effort=entry.supported_effort,
                    provider=entry.provider,
                    model=entry.model,
                )
                for entry in catalog.models
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/auth-status",
    response_model=EngineAuthStatusResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_engine_auth_status():
    return EngineAuthStatusResponse(engines=agent_cli_manager.collect_auth_status())


@router.post(
    "/auth/oauth-proxy/sessions",
    response_model=AuthSessionSnapshotV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def start_oauth_proxy_auth_session(request: Request, body: AuthSessionStartRequestV2):
    if body.transport.strip().lower() != "oauth_proxy":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="transport must be oauth_proxy")
    try:
        payload = oauth_proxy_orchestrator.start_session(
            engine=body.engine,
            auth_method=body.auth_method,
            provider_id=body.provider_id,
            callback_base_url=str(request.base_url).rstrip("/"),
        )
        return AuthSessionSnapshotV2(**payload)
    except EngineInteractionBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/auth/oauth-proxy/sessions/{session_id}",
    response_model=AuthSessionSnapshotV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_oauth_proxy_auth_session(session_id: str):
    try:
        payload = oauth_proxy_orchestrator.get_session(session_id)
        return AuthSessionSnapshotV2(**payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/oauth-proxy/sessions/{session_id}/input",
    response_model=AuthSessionInputResponseV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def input_oauth_proxy_auth_session(session_id: str, body: AuthSessionInputRequestV2):
    try:
        payload = oauth_proxy_orchestrator.input_session(session_id, body.kind, body.value)
        return AuthSessionInputResponseV2(
            session=AuthSessionSnapshotV2(**payload),
            accepted=str(payload.get("status")) in {"code_submitted_waiting_result", "succeeded"},
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/oauth-proxy/sessions/{session_id}/cancel",
    response_model=AuthSessionCancelResponseV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def cancel_oauth_proxy_auth_session(session_id: str):
    try:
        payload = oauth_proxy_orchestrator.cancel_session(session_id)
        return AuthSessionCancelResponseV2(
            session=AuthSessionSnapshotV2(**payload),
            canceled=str(payload.get("status")) == "canceled",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/oauth-proxy/callback/openai", response_class=HTMLResponse)
async def handle_openai_oauth_proxy_callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
):
    try:
        callback_payload = oauth_callback_router.parse(
            state=state,
            code=code,
            error=error,
        )
        payload = oauth_callback_router.execute(
            callback_payload,
            lambda *, state, code=None, error=None: oauth_proxy_orchestrator.complete_callback(
                channel="openai",
                state=state,
                code=code,
                error=error,
            ),
        )
    except ValueError as exc:
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return oauth_callback_router.render(payload)


@router.post(
    "/auth/cli-delegate/sessions",
    response_model=AuthSessionSnapshotV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def start_cli_delegate_auth_session(request: Request, body: AuthSessionStartRequestV2):
    if body.transport.strip().lower() != "cli_delegate":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="transport must be cli_delegate")
    try:
        payload = cli_delegate_orchestrator.start_session(
            engine=body.engine,
            auth_method=body.auth_method,
            provider_id=body.provider_id,
            callback_base_url=str(request.base_url).rstrip("/"),
        )
        return AuthSessionSnapshotV2(**payload)
    except EngineInteractionBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/auth/cli-delegate/sessions/{session_id}",
    response_model=AuthSessionSnapshotV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_cli_delegate_auth_session(session_id: str):
    try:
        payload = cli_delegate_orchestrator.get_session(session_id)
        return AuthSessionSnapshotV2(**payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/cli-delegate/sessions/{session_id}/input",
    response_model=AuthSessionInputResponseV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def input_cli_delegate_auth_session(session_id: str, body: AuthSessionInputRequestV2):
    try:
        payload = cli_delegate_orchestrator.input_session(session_id, body.kind, body.value)
        return AuthSessionInputResponseV2(
            session=AuthSessionSnapshotV2(**payload),
            accepted=str(payload.get("status")) in {"code_submitted_waiting_result", "succeeded"},
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/cli-delegate/sessions/{session_id}/cancel",
    response_model=AuthSessionCancelResponseV2,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def cancel_cli_delegate_auth_session(session_id: str):
    try:
        payload = cli_delegate_orchestrator.cancel_session(session_id)
        return AuthSessionCancelResponseV2(
            session=AuthSessionSnapshotV2(**payload),
            canceled=str(payload.get("status")) == "canceled",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/sessions",
    response_model=EngineAuthSessionSnapshot,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def start_engine_auth_session(request: Request, body: EngineAuthSessionStartRequest):
    try:
        payload = engine_auth_flow_manager.start_session(
            engine=body.engine,
            method=body.method,
            auth_method=body.auth_method,
            provider_id=body.provider_id,
            transport=body.transport,
            callback_base_url=str(request.base_url).rstrip("/"),
        )
        payload["deprecated"] = True
        return EngineAuthSessionSnapshot(**payload)
    except EngineInteractionBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback/openai", response_class=HTMLResponse)
async def handle_openai_oauth_callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
):
    try:
        callback_payload = oauth_callback_router.parse(
            state=state,
            code=code,
            error=error,
        )
        payload = oauth_callback_router.execute(
            callback_payload,
            lambda *, state, code=None, error=None: engine_auth_flow_manager.complete_callback(
                channel="openai",
                state=state,
                code=code,
                error=error,
            ),
        )
    except ValueError as exc:
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return oauth_callback_router.render(payload)


@router.get(
    "/auth/sessions/{session_id}",
    response_model=EngineAuthSessionSnapshot,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_engine_auth_session(session_id: str):
    try:
        payload = engine_auth_flow_manager.get_session(session_id)
        payload["deprecated"] = True
        return EngineAuthSessionSnapshot(**payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/sessions/{session_id}/cancel",
    response_model=EngineAuthSessionCancelResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def cancel_engine_auth_session(session_id: str):
    try:
        payload = engine_auth_flow_manager.cancel_session(session_id)
        payload["deprecated"] = True
        return EngineAuthSessionCancelResponse(
            session=EngineAuthSessionSnapshot(**payload),
            canceled=str(payload.get("status")) == "canceled",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auth/sessions/{session_id}/input",
    response_model=EngineAuthSessionInputResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def input_engine_auth_session(session_id: str, body: EngineAuthSessionInputRequest):
    try:
        payload = engine_auth_flow_manager.input_session(session_id, body.kind, body.value)
        payload["deprecated"] = True
        return EngineAuthSessionInputResponse(
            session=EngineAuthSessionSnapshot(**payload),
            accepted=str(payload.get("status"))
            in {"code_submitted_waiting_result", "succeeded"},
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{engine}/models/manifest",
    response_model=EngineManifestViewResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_manifest_view(engine: str):
    try:
        view = model_registry.get_manifest_view(engine)
        return EngineManifestViewResponse(
            engine=view["engine"],
            cli_version_detected=view["cli_version_detected"],
            manifest=view["manifest"],
            resolved_snapshot_version=view["resolved_snapshot_version"],
            resolved_snapshot_file=view["resolved_snapshot_file"],
            fallback_reason=view["fallback_reason"],
            models=[
                EngineManifestModelInfo(
                    id=model["id"],
                    display_name=model.get("display_name"),
                    deprecated=bool(model.get("deprecated", False)),
                    notes=model.get("notes"),
                    supported_effort=model.get("supported_effort"),
                    provider=model.get("provider"),
                    model=model.get("model"),
                )
                for model in view["models"]
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{engine}/models/snapshots",
    response_model=EngineManifestViewResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def add_manifest_snapshot(engine: str, body: EngineSnapshotCreateRequest):
    try:
        view = model_registry.add_snapshot_for_detected_version(
            engine,
            [model.model_dump() for model in body.models],
        )
        return EngineManifestViewResponse(
            engine=view["engine"],
            cli_version_detected=view["cli_version_detected"],
            manifest=view["manifest"],
            resolved_snapshot_version=view["resolved_snapshot_version"],
            resolved_snapshot_file=view["resolved_snapshot_file"],
            fallback_reason=view["fallback_reason"],
            models=[
                EngineManifestModelInfo(
                    id=model["id"],
                    display_name=model.get("display_name"),
                    deprecated=bool(model.get("deprecated", False)),
                    notes=model.get("notes"),
                    supported_effort=model.get("supported_effort"),
                    provider=model.get("provider"),
                    model=model.get("model"),
                )
                for model in view["models"]
            ],
        )
    except ValueError as e:
        detail = str(e)
        if "does not support model snapshots" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        if "Snapshot already exists" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        if "CLI version not detected" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upgrades",
    response_model=EngineUpgradeCreateResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def create_engine_upgrade(body: EngineUpgradeCreateRequest):
    try:
        request_id = engine_upgrade_manager.create_task(body.mode, body.engine)
    except EngineUpgradeBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except EngineUpgradeValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return EngineUpgradeCreateResponse(
        request_id=request_id,
        status=EngineUpgradeTaskStatus.QUEUED,
    )


@router.get(
    "/upgrades/{request_id}",
    response_model=EngineUpgradeStatusResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def get_engine_upgrade(request_id: str):
    record = engine_upgrade_manager.get_task(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Upgrade request not found")

    requested_engine_obj = record.get("requested_engine")
    requested_engine = requested_engine_obj if isinstance(requested_engine_obj, str) else None

    results_obj = record.get("results")
    results_payload = results_obj if isinstance(results_obj, dict) else {}

    created_at_obj = record.get("created_at")
    updated_at_obj = record.get("updated_at")
    if isinstance(created_at_obj, datetime):
        created_at = created_at_obj
    else:
        created_at = datetime.fromisoformat(str(created_at_obj))
    if isinstance(updated_at_obj, datetime):
        updated_at = updated_at_obj
    else:
        updated_at = datetime.fromisoformat(str(updated_at_obj))

    return EngineUpgradeStatusResponse(
        request_id=str(record["request_id"]),
        mode=str(record["mode"]),
        requested_engine=requested_engine,
        status=EngineUpgradeTaskStatus(str(record["status"])),
        results={
            engine: EngineUpgradeEngineResult(**result)
            for engine, result in results_payload.items()
        },
        created_at=created_at,
        updated_at=updated_at,
    )
