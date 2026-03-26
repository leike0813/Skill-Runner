from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, cast
from jinja2 import pass_context

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse  # type: ignore[import-not-found]
from fastapi.templating import Jinja2Templates  # type: ignore[import-not-found]

from .backend import (
    RUN_SOURCE_INSTALLED,
    RUN_SOURCE_TEMP,
    BackendApiError,
    BackendClient,
    HttpBackendClient,
    RunSource,
)
from .config import E2EClientSettings
from server.i18n import get_language, get_translator


TEMPLATE_ROOT = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))


@pass_context
def _template_translate(context, key: str, default: str | None = None, **kwargs):
    request = context.get("request")
    if request is not None and hasattr(request.state, "t"):
        return request.state.t(key, default=default, **kwargs)
    if request is not None:
        translator = get_translator(request)
        return translator(key, default=default, **kwargs)
    return default if default is not None else key


@pass_context
def _template_lang(context):
    request = context.get("request")
    if request is None:
        return "zh"
    return getattr(request.state, "lang", get_language(request))


templates.env.globals["t"] = _template_translate
templates.env.globals["lang"] = _template_lang

router = APIRouter(tags=["e2e-client"])

RUNTIME_BOOL_OPTIONS = ("no_cache", "interactive_auto_reply")
RUNTIME_TIMEOUT_OPTIONS = ("interactive_reply_timeout_sec", "hard_timeout_seconds")
VALID_RUN_SOURCES = {RUN_SOURCE_INSTALLED, RUN_SOURCE_TEMP}
ENGINE_DEFAULT_PROVIDER = {
    "codex": "openai",
    "gemini": "google",
    "iflow": "iflowcn",
}


def _to_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, BackendApiError):
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    if isinstance(exc, (httpx.RequestError, httpx.TimeoutException)):
        return HTTPException(status_code=503, detail="backend_unreachable")
    return HTTPException(status_code=500, detail="internal_e2e_proxy_error")


def _sse_error_frame(*, detail: Any, status_code: int) -> bytes:
    payload = {"error": detail, "status_code": status_code}
    frame = f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return frame.encode("utf-8")


def get_settings(request: Request) -> E2EClientSettings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, E2EClientSettings):
        raise RuntimeError("E2E client settings are not configured")
    return settings


def get_backend_client(
    settings: E2EClientSettings = Depends(get_settings),
) -> BackendClient:
    return HttpBackendClient(settings.backend_base_url)


async def _list_management_runs_compat(
    backend: BackendClient,
    *,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    try:
        return await backend.list_management_runs(
            page=page,
            page_size=page_size,
        )
    except TypeError:
        # Backward-compat for tests/fakes still implementing legacy signature.
        return await backend.list_management_runs()


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    backend: BackendClient = Depends(get_backend_client),
    settings: E2EClientSettings = Depends(get_settings),
):
    try:
        payload = await backend.list_skills()
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    supported_engines = await _load_supported_engines(backend)
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "skills": _normalize_home_skills_rows(skills),
            "fixture_skills": _list_fixture_skills(
                settings,
                fallback_engines=supported_engines,
            ),
        },
    )


@router.get("/skills/{skill_id}/run", response_class=HTMLResponse)
async def run_form_page(
    request: Request,
    skill_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    detail, schemas = await _load_skill_bundle(backend, skill_id)
    service_runtime_defaults = await _load_service_runtime_defaults(backend)
    engine_models_by_engine = await _load_engine_models(backend, detail)
    return templates.TemplateResponse(
        request=request,
        name="run_form.html",
        context=_build_run_form_context(
            skill=detail,
            schemas=schemas,
            service_runtime_defaults=service_runtime_defaults,
            engine_models_by_engine=engine_models_by_engine,
            errors=[],
            run_source=RUN_SOURCE_INSTALLED,
            form_action=f"/skills/{skill_id}/run",
            submitted={
                "engine": "",
                "provider": "",
                "execution_mode": "",
                "model": "",
                "runtime_options": {},
                "input": {},
                "parameter": {},
            },
        ),
    )


@router.get("/fixtures/{fixture_skill_id}/run", response_class=HTMLResponse)
async def fixture_run_form_page(
    request: Request,
    fixture_skill_id: str,
    settings: E2EClientSettings = Depends(get_settings),
    backend: BackendClient = Depends(get_backend_client),
):
    supported_engines = await _load_supported_engines(backend)
    service_runtime_defaults = await _load_service_runtime_defaults(backend)
    detail, schemas = _load_fixture_skill_bundle(
        settings,
        fixture_skill_id,
        fallback_engines=supported_engines,
    )
    engine_models_by_engine = await _load_engine_models(backend, detail)
    return templates.TemplateResponse(
        request=request,
        name="run_form.html",
        context=_build_run_form_context(
            skill=detail,
            schemas=schemas,
            service_runtime_defaults=service_runtime_defaults,
            engine_models_by_engine=engine_models_by_engine,
            errors=[],
            run_source=RUN_SOURCE_TEMP,
            form_action=f"/fixtures/{fixture_skill_id}/run",
            submitted={
                "engine": "",
                "provider": "",
                "execution_mode": "",
                "model": "",
                "runtime_options": {},
                "input": {},
                "parameter": {},
            },
        ),
    )


@router.post("/skills/{skill_id}/run", response_class=HTMLResponse)
async def submit_run(
    request: Request,
    skill_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    detail, schemas = await _load_skill_bundle(backend, skill_id)
    service_runtime_defaults = await _load_service_runtime_defaults(backend)
    engine_models_by_engine = await _load_engine_models(backend, detail)
    submission = await _collect_run_submission(
        request=request,
        detail=detail,
        schemas=schemas,
        engine_models_by_engine=engine_models_by_engine,
        run_source=RUN_SOURCE_INSTALLED,
    )
    if submission["errors"]:
        return templates.TemplateResponse(
            request=request,
            name="run_form.html",
            context=_build_run_form_context(
                skill=detail,
                schemas=schemas,
                service_runtime_defaults=service_runtime_defaults,
                engine_models_by_engine=engine_models_by_engine,
                errors=cast(list[str], submission["errors"]),
                run_source=RUN_SOURCE_INSTALLED,
                form_action=f"/skills/{skill_id}/run",
                submitted={
                    "engine": submission["engine_for_form"],
                    "provider": submission["provider_for_form"],
                    "execution_mode": submission["execution_mode_for_form"],
                    "model": submission["model_for_form"],
                    "runtime_options": submission["submitted_runtime_options"],
                    "input": submission["combined_input"],
                    "parameter": submission["parameter_input"],
                },
            ),
            status_code=400,
        )

    create_payload = {
        "skill_id": skill_id,
        "engine": submission["engine"],
        "input": submission["combined_input"],
        "parameter": submission["parameter_input"],
        "runtime_options": submission["runtime_options"],
    }
    if submission["selected_model"]:
        create_payload["model"] = submission["selected_model"]

    try:
        create_response = await backend.create_run(create_payload)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    request_id_raw = create_response.get("request_id")
    if not isinstance(request_id_raw, str) or not request_id_raw:
        raise HTTPException(status_code=502, detail="Missing request_id in backend response")
    request_id = request_id_raw

    uploaded_files = cast(dict[str, bytes], submission["uploaded_files"])
    if uploaded_files:
        zip_bytes = _build_upload_zip(uploaded_files)
        try:
            upload_response = await backend.upload_run_file(request_id, zip_bytes)
        except BackendApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        _ = upload_response

    return RedirectResponse(
        url=f"/runs/{request_id}",
        status_code=303,
    )


@router.post("/fixtures/{fixture_skill_id}/run", response_class=HTMLResponse)
async def submit_fixture_run(
    request: Request,
    fixture_skill_id: str,
    settings: E2EClientSettings = Depends(get_settings),
    backend: BackendClient = Depends(get_backend_client),
):
    supported_engines = await _load_supported_engines(backend)
    service_runtime_defaults = await _load_service_runtime_defaults(backend)
    detail, schemas = _load_fixture_skill_bundle(
        settings,
        fixture_skill_id,
        fallback_engines=supported_engines,
    )
    engine_models_by_engine = await _load_engine_models(backend, detail)
    submission = await _collect_run_submission(
        request=request,
        detail=detail,
        schemas=schemas,
        engine_models_by_engine=engine_models_by_engine,
        run_source=RUN_SOURCE_TEMP,
    )
    if submission["errors"]:
        return templates.TemplateResponse(
            request=request,
            name="run_form.html",
            context=_build_run_form_context(
                skill=detail,
                schemas=schemas,
                service_runtime_defaults=service_runtime_defaults,
                engine_models_by_engine=engine_models_by_engine,
                errors=cast(list[str], submission["errors"]),
                run_source=RUN_SOURCE_TEMP,
                form_action=f"/fixtures/{fixture_skill_id}/run",
                submitted={
                    "engine": submission["engine_for_form"],
                    "provider": submission["provider_for_form"],
                    "execution_mode": submission["execution_mode_for_form"],
                    "model": submission["model_for_form"],
                    "runtime_options": submission["submitted_runtime_options"],
                    "input": submission["combined_input"],
                    "parameter": submission["parameter_input"],
                },
            ),
            status_code=400,
        )

    create_payload = {
        "engine": submission["engine"],
        "input": submission["combined_input"],
        "parameter": submission["parameter_input"],
        "runtime_options": submission["runtime_options"],
    }
    if submission["selected_model"]:
        create_payload["model"] = submission["selected_model"]

    try:
        create_response = await backend.create_temp_run(create_payload)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    request_id_raw = create_response.get("request_id")
    if not isinstance(request_id_raw, str) or not request_id_raw:
        raise HTTPException(status_code=502, detail="Missing request_id in backend response")
    request_id = request_id_raw

    skill_package_zip = _build_fixture_skill_package_zip(settings, fixture_skill_id)
    uploaded_files = cast(dict[str, bytes], submission["uploaded_files"])
    input_zip = _build_upload_zip(uploaded_files) if uploaded_files else None
    try:
        upload_response = await backend.upload_temp_run(
            request_id,
            skill_package_zip=skill_package_zip,
            input_zip=input_zip,
        )
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    _ = upload_response

    return RedirectResponse(
        url=f"/runs/{request_id}",
        status_code=303,
    )


@router.get("/runs/{request_id}", response_class=HTMLResponse)
async def run_observe_page(
    request: Request,
    request_id: str,
    source: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    return templates.TemplateResponse(
        request=request,
        name="run_observe.html",
        context={
            "request_id": request_id,
            "run_source": run_source,
            "return_page": max(1, int(page)),
            "return_page_size": max(1, int(page_size)),
        },
    )


@router.get("/runs", response_class=HTMLResponse)
async def list_runs_page(
    request: Request,
    backend: BackendClient = Depends(get_backend_client),
    page: int = 1,
    page_size: int = 20,
):
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 200))
    try:
        payload = await _list_management_runs_compat(
            backend,
            page=safe_page,
            page_size=safe_page_size,
        )
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    raw_runs = payload.get("runs", [])
    rows = raw_runs if isinstance(raw_runs, list) else []
    run_rows: list[dict[str, Any]] = []
    for row in rows:
        request_id = str(row.get("request_id") or "")
        run_source = _resolve_run_source(
            source=row.get("run_source"),
            request_id=request_id,
        )
        summary = {
            "status": str(row.get("status") or "unknown"),
            "run_id": str(row.get("run_id") or "-"),
            "skill_id": str(row.get("skill_id") or "-"),
            "engine": str(row.get("engine") or "-"),
            "state_error": None,
        }
        run_rows.append(
            {
                "request_id": request_id,
                "run_source": run_source,
                "updated_at": row.get("updated_at"),
                "step_count": 0,
                "model": str(row.get("model") or "-"),
                **summary,
            }
        )
    total = int(payload.get("total") or len(run_rows))
    total_pages = int(payload.get("total_pages") or (1 if run_rows else 0))
    current_page = int(payload.get("page") or safe_page)
    current_page_size = int(payload.get("page_size") or safe_page_size)
    return templates.TemplateResponse(
        request=request,
        name="runs.html",
        context={
            "rows": run_rows,
            "page": current_page,
            "page_size": current_page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/api/runs/{request_id}")
async def get_run_state_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        return await backend.get_run_state(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/pending")
async def get_run_pending_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        return await backend.get_run_pending(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/bundle/entries")
async def get_run_bundle_entries_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        payload = await backend.get_run_files(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)
    entries_obj = payload.get("entries")
    entries = entries_obj if isinstance(entries_obj, list) else []
    return {"request_id": request_id, "entries": entries}


@router.get("/api/runs/{request_id}/bundle/download")
async def download_run_bundle_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        bundle_bytes = await backend.get_run_bundle(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)
    filename = f"{request_id}.bundle.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers=headers,
    )


@router.get("/api/runs/{request_id}/bundle/debug/download")
async def download_run_debug_bundle_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        bundle_bytes = await backend.get_run_debug_bundle(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)
    filename = f"{request_id}.debug.bundle.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers=headers,
    )


@router.get("/api/runs/{request_id}/bundle/file")
async def get_run_bundle_file_api(
    request_id: str,
    path: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        payload = await backend.get_run_file_preview(
            request_id,
            path=path,
            run_source=run_source,
        )
    except Exception as exc:
        raise _to_http_exception(exc)
    preview_obj = payload.get("preview")
    preview = preview_obj if isinstance(preview_obj, dict) else {}
    return {"request_id": request_id, "path": path, "preview": preview}


@router.get("/runs/{request_id}/bundle/view", response_class=HTMLResponse)
async def get_run_bundle_file_view(
    request: Request,
    request_id: str,
    path: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        payload = await backend.get_run_file_preview(
            request_id,
            path=path,
            run_source=run_source,
        )
    except Exception as exc:
        raise _to_http_exception(exc)
    preview_obj = payload.get("preview")
    preview = preview_obj if isinstance(preview_obj, dict) else {}
    return templates.TemplateResponse(
        request=request,
        name="partials/file_preview.html",
        context={
            "relative_path": path,
            "preview": preview,
        },
    )


@router.post("/api/runs/{request_id}/reply")
async def post_run_reply_api(
    request_id: str,
    request: Request,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Reply payload must be an object")
    try:
        reply = await backend.post_run_reply(request_id, payload, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)
    return reply


@router.post("/api/runs/{request_id}/auth/import")
async def post_run_auth_import_api(
    request_id: str,
    request: Request,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    form = await request.form()
    provider_raw = form.get("provider_id")
    provider_id = str(provider_raw).strip() if provider_raw is not None else None
    uploaded_files: list[tuple[str, bytes]] = []
    for item in form.getlist("files"):
        filename = getattr(item, "filename", None)
        if not isinstance(filename, str) or not filename.strip():
            continue
        reader = getattr(item, "read", None)
        if not callable(reader):
            continue
        content = await reader()
        uploaded_files.append((filename.strip(), content))
    try:
        return await backend.post_run_auth_import(
            request_id,
            files=uploaded_files,
            provider_id=provider_id,
            run_source=run_source,
        )
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/events")
async def stream_run_events_api(
    request_id: str,
    source: str | None = None,
    cursor: int = 0,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    async def _stream():
        try:
            async for chunk in backend.stream_run_events(
                request_id,
                run_source=run_source,
                cursor=cursor,
            ):
                yield chunk
        except BackendApiError as exc:
            yield _sse_error_frame(detail=exc.detail, status_code=exc.status_code)
        except Exception as exc:
            mapped = _to_http_exception(exc)
            yield _sse_error_frame(detail=mapped.detail, status_code=mapped.status_code)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/runs/{request_id}/events/history")
async def get_run_events_history_api(
    request_id: str,
    source: str | None = None,
    from_seq: int | None = None,
    to_seq: int | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        return await backend.get_run_event_history(
            request_id,
            run_source=run_source,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/chat")
async def stream_run_chat_api(
    request_id: str,
    source: str | None = None,
    cursor: int = 0,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)

    async def _stream():
        try:
            async for chunk in backend.stream_run_chat(
                request_id,
                run_source=run_source,
                cursor=cursor,
            ):
                yield chunk
        except BackendApiError as exc:
            yield _sse_error_frame(detail=exc.detail, status_code=exc.status_code)
        except Exception as exc:
            mapped = _to_http_exception(exc)
            yield _sse_error_frame(detail=mapped.detail, status_code=mapped.status_code)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/runs/{request_id}/chat/history")
async def get_run_chat_history_api(
    request_id: str,
    source: str | None = None,
    from_seq: int | None = None,
    to_seq: int | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        return await backend.get_run_chat_history(
            request_id,
            run_source=run_source,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/logs/range")
async def get_run_logs_range_api(
    request_id: str,
    stream: str,
    source: str | None = None,
    byte_from: int = 0,
    byte_to: int = 0,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        return await backend.get_run_log_range(
            request_id,
            run_source=run_source,
            stream=stream,
            byte_from=byte_from,
            byte_to=byte_to,
        )
    except Exception as exc:
        raise _to_http_exception(exc)


@router.get("/api/runs/{request_id}/final-summary")
async def get_run_final_summary_api(
    request_id: str,
    source: str | None = None,
    backend: BackendClient = Depends(get_backend_client),
):
    run_source = _resolve_run_source(source=source, request_id=request_id)
    try:
        payload = await backend.get_run_final_summary(request_id, run_source=run_source)
    except Exception as exc:
        raise _to_http_exception(exc)
    artifacts_raw = payload.get("artifacts")
    artifacts = artifacts_raw if isinstance(artifacts_raw, list) else []
    result_obj = payload.get("result")
    result_preview = _build_result_preview(result_obj)
    result_status = ""
    result_error_code = ""
    result_error_message = ""
    if isinstance(result_obj, dict):
        status_obj = result_obj.get("status")
        if isinstance(status_obj, str) and status_obj.strip():
            result_status = status_obj.strip().lower()
        error_obj = result_obj.get("error")
        if isinstance(error_obj, dict):
            code_obj = error_obj.get("code")
            if isinstance(code_obj, str) and code_obj.strip():
                result_error_code = code_obj.strip()
            message_obj = error_obj.get("message")
            if isinstance(message_obj, str) and message_obj.strip():
                result_error_message = message_obj.strip()
    return {
        "request_id": request_id,
        "has_result": bool(result_obj),
        "has_artifacts": bool(artifacts),
        "artifacts": artifacts,
        "result_preview": result_preview,
        "result_status": result_status,
        "result_error_code": result_error_code,
        "result_error_message": result_error_message,
    }


async def _load_skill_bundle(
    backend: BackendClient,
    skill_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        detail = await backend.get_skill_detail(skill_id)
        schemas = await backend.get_skill_schemas(skill_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if not isinstance(detail, dict):
        raise HTTPException(status_code=502, detail="Invalid skill detail payload")
    if not isinstance(schemas, dict):
        raise HTTPException(status_code=502, detail="Invalid skill schemas payload")
    return detail, schemas


async def _load_service_runtime_defaults(
    backend: BackendClient,
) -> dict[str, int]:
    try:
        payload = await backend.get_runtime_options()
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Invalid runtime options payload")
    service_defaults = payload.get("service_defaults")
    if not isinstance(service_defaults, dict):
        raise HTTPException(status_code=502, detail="Invalid runtime options payload")
    hard_timeout_value = _coerce_non_negative_int(service_defaults.get("hard_timeout_seconds"))
    if hard_timeout_value is None:
        raise HTTPException(status_code=502, detail="Invalid runtime options payload")
    return {"hard_timeout_seconds": hard_timeout_value}


async def _load_engine_models(
    backend: BackendClient,
    skill_detail: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    engine_models_by_engine: dict[str, list[dict[str, Any]]] = {}
    engines = _extract_engines(skill_detail)
    for engine in engines:
        try:
            detail = await backend.get_engine_detail(engine)
        except BackendApiError:
            engine_models_by_engine[engine] = []
            continue
        raw_models = detail.get("models", [])
        models: list[dict[str, Any]] = []
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    models.append(item)
        engine_models_by_engine[engine] = models
    return engine_models_by_engine


async def _load_supported_engines(backend: BackendClient) -> list[str]:
    try:
        payload = await backend.list_management_engines()
    except BackendApiError:
        return []
    if not isinstance(payload, dict):
        return []
    return _extract_management_engine_names(payload)


async def _collect_run_submission(
    *,
    request: Request,
    detail: Mapping[str, Any],
    schemas: Mapping[str, Any],
    engine_models_by_engine: dict[str, list[dict[str, Any]]],
    run_source: RunSource,
) -> dict[str, Any]:
    run_form = await request.form()
    submitted_engine = str(run_form.get("engine", "") or "")
    submitted_execution_mode = str(run_form.get("execution_mode", "") or "")
    submitted_provider = str(run_form.get("provider", "") or "").strip()
    submitted_model = str(run_form.get("model", "") or "").strip()
    submitted_model_value = str(run_form.get("model_value", "") or "").strip()
    submitted_runtime_options = _collect_submitted_runtime_options(run_form)

    engine = _resolve_engine(submitted_engine, detail)
    if not submitted_model and submitted_model_value:
        if engine == "opencode":
            if "/" in submitted_model_value:
                submitted_model = submitted_model_value
            elif submitted_provider:
                submitted_model = f"{submitted_provider}/{submitted_model_value}"
        else:
            submitted_model = submitted_model_value
    execution_mode, mode_error = _resolve_execution_mode(submitted_execution_mode, detail)
    selected_model, model_error = _resolve_model(
        selected=submitted_model,
        allowed_models=_extract_engine_model_ids(engine_models_by_engine, engine),
    )
    provider_for_form = submitted_provider or _derive_provider_from_model(selected_model, engine=engine)
    if not provider_for_form:
        provider_for_form = ENGINE_DEFAULT_PROVIDER.get(engine, "")
    runtime_options, runtime_errors = _build_runtime_options(
        execution_mode=execution_mode,
        submitted=submitted_runtime_options,
        run_source=run_source,
    )

    inline_schema = _as_schema_dict(schemas.get("input"))
    parameter_schema = _as_schema_dict(schemas.get("parameter"))
    input_fields = _extract_input_fields(inline_schema)
    parameter_fields = _extract_object_fields(parameter_schema)

    inline_input, input_errors = _collect_scalar_values(
        run_form=run_form,
        field_prefix="input__",
        fields=input_fields["inline_fields"],
    )
    parameter_input, parameter_errors = _collect_scalar_values(
        run_form=run_form,
        field_prefix="parameter__",
        fields=parameter_fields,
    )
    uploaded_files, file_input_values, file_errors = await _collect_file_values(
        run_form=run_form,
        file_fields=input_fields["file_fields"],
    )
    combined_input = dict(inline_input)
    combined_input.update(file_input_values)

    errors = input_errors + parameter_errors + file_errors + runtime_errors
    if mode_error:
        errors.append(mode_error)
    if model_error:
        errors.append(model_error)
    return {
        "errors": errors,
        "engine": engine,
        "engine_for_form": engine,
        "provider_for_form": provider_for_form,
        "execution_mode": execution_mode,
        "execution_mode_for_form": execution_mode if not mode_error else submitted_execution_mode,
        "selected_model": selected_model,
        "model_for_form": selected_model if not model_error else submitted_model,
        "runtime_options": runtime_options,
        "submitted_runtime_options": submitted_runtime_options,
        "inline_input": inline_input,
        "file_input_values": file_input_values,
        "combined_input": combined_input,
        "parameter_input": parameter_input,
        "uploaded_files": uploaded_files,
    }


def _list_fixture_skills(
    settings: E2EClientSettings,
    *,
    fallback_engines: list[str] | None = None,
) -> list[dict[str, Any]]:
    root = settings.fixtures_skills_dir
    if not root.exists() or not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        try:
            detail, _ = _load_fixture_skill_bundle_from_dir(
                path,
                path.name,
                fallback_engines=fallback_engines,
            )
        except Exception:
            continue
        rows.append(
            {
                "fixture_skill_id": path.name,
                "id": detail.get("id"),
                "name": detail.get("name"),
                "version": detail.get("version"),
                "engines": _extract_engines(detail),
                "execution_modes": _extract_execution_modes(detail),
            }
        )
    return rows


def _load_fixture_skill_bundle(
    settings: E2EClientSettings,
    fixture_skill_id: str,
    *,
    fallback_engines: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    skill_dir = _resolve_fixture_skill_dir(settings.fixtures_skills_dir, fixture_skill_id)
    try:
        return _load_fixture_skill_bundle_from_dir(
            skill_dir,
            fixture_skill_id,
            fallback_engines=fallback_engines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _load_fixture_skill_bundle_from_dir(
    skill_dir: Path,
    fixture_skill_id: str,
    *,
    fallback_engines: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runner_path = skill_dir / "assets" / "runner.json"
    if not runner_path.exists() or not runner_path.is_file():
        raise ValueError("Fixture skill runner.json not found")
    runner = _read_json_object(runner_path)
    if not isinstance(runner, dict):
        raise ValueError("Fixture runner.json is invalid")
    schemas_decl = runner.get("schemas")
    schemas_map = schemas_decl if isinstance(schemas_decl, dict) else {}
    input_schema = _read_fixture_schema(skill_dir, schemas_map.get("input"))
    parameter_schema = _read_fixture_schema(skill_dir, schemas_map.get("parameter"))
    output_schema = _read_fixture_schema(skill_dir, schemas_map.get("output"))
    declared_engines = _normalize_str_list(runner.get("engines"))
    effective_engines = _normalize_str_list(runner.get("effective_engines"))
    if not effective_engines:
        effective_engines = declared_engines
    if not effective_engines:
        effective_engines = _normalize_str_list(fallback_engines or [])
    execution_modes = _normalize_str_list(runner.get("execution_modes")) or ["auto"]
    skill_id = _coerce_non_empty_str(runner.get("id"), fixture_skill_id)
    skill_name = _coerce_non_empty_str(runner.get("name"), skill_id)
    skill_version = _coerce_non_empty_str(runner.get("version"), "0.0.0")
    detail = {
        "id": skill_id,
        "name": skill_name,
        "version": skill_version,
        "engines": declared_engines,
        "effective_engines": effective_engines,
        "execution_modes": execution_modes,
        "runtime": _normalize_fixture_runtime(runner.get("runtime")),
        "fixture_skill_id": fixture_skill_id,
    }
    schemas = {
        "skill_id": skill_id,
        "input": input_schema,
        "parameter": parameter_schema,
        "output": output_schema,
    }
    return detail, schemas


def _resolve_fixture_skill_dir(root: Path, fixture_skill_id: str) -> Path:
    normalized = _normalize_bundle_request_path(fixture_skill_id)
    if "/" in normalized:
        raise HTTPException(status_code=400, detail="Invalid fixture skill id")
    root_resolved = root.resolve()
    if not root_resolved.exists() or not root_resolved.is_dir():
        raise HTTPException(status_code=404, detail="Fixture skill root not found")
    candidate = (root_resolved / normalized).resolve()
    if not candidate.is_dir() or not _is_path_inside_root(candidate, root_resolved):
        raise HTTPException(status_code=404, detail="Fixture skill not found")
    return candidate


def _read_fixture_schema(skill_dir: Path, schema_path: Any) -> dict[str, Any]:
    if not isinstance(schema_path, str) or not schema_path.strip():
        return {}
    target = _resolve_relative_path(skill_dir, schema_path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"Fixture schema not found: {schema_path}")
    payload = _read_json_object(target)
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Fixture schema is invalid: {schema_path}")


def _read_json_object(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_relative_path(root: Path, relative_path: str) -> Path:
    normalized = _normalize_bundle_request_path(relative_path)
    root_resolved = root.resolve()
    candidate = (root_resolved / normalized).resolve()
    if not _is_path_inside_root(candidate, root_resolved):
        raise ValueError("invalid relative path")
    return candidate


def _is_path_inside_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for item in raw:
        if isinstance(item, str):
            value = item.strip()
            if value:
                items.append(value)
    return list(dict.fromkeys(items))


def _coerce_non_empty_str(raw: Any, default: str) -> str:
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            return value
    return default


def _coerce_non_negative_int(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _normalize_fixture_runtime(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"default_options": {}}
    default_options_obj = raw.get("default_options")
    if not isinstance(default_options_obj, dict):
        return {"default_options": {}}
    return {
        "default_options": {
            str(key): value
            for key, value in default_options_obj.items()
            if isinstance(key, str)
        }
    }


def _build_fixture_skill_package_zip(
    settings: E2EClientSettings,
    fixture_skill_id: str,
) -> bytes:
    skill_dir = _resolve_fixture_skill_dir(settings.fixtures_skills_dir, fixture_skill_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(skill_dir).as_posix()
            archive.writestr(f"{fixture_skill_id}/{rel_path}", path.read_bytes())
    return buffer.getvalue()


def _normalize_run_source(raw: Any) -> RunSource | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if value not in VALID_RUN_SOURCES:
        return None
    return cast(RunSource, value)


def _resolve_run_source(
    *,
    source: Any,
    request_id: str,
) -> RunSource:
    _ = source
    _ = request_id
    return RUN_SOURCE_INSTALLED


def _build_result_preview(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result[:600]
    try:
        serialized = json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)[:600]
    return serialized[:600]


def _build_run_form_context(
    *,
    skill: dict[str, Any],
    schemas: dict[str, Any],
    service_runtime_defaults: dict[str, int],
    engine_models_by_engine: dict[str, list[dict[str, Any]]],
    errors: list[str],
    run_source: RunSource,
    form_action: str,
    submitted: dict[str, Any],
) -> dict[str, Any]:
    input_schema = _as_schema_dict(schemas.get("input"))
    parameter_schema = _as_schema_dict(schemas.get("parameter"))
    input_fields = _extract_input_fields(input_schema)
    parameter_fields = _extract_object_fields(parameter_schema)
    engines = _extract_engines(skill)
    execution_modes = _extract_execution_modes(skill)
    selected_engine = str(submitted.get("engine") or "")
    if not selected_engine and engines:
        selected_engine = str(engines[0])
    selected_execution_mode = str(submitted.get("execution_mode") or "")
    if not selected_execution_mode and execution_modes:
        selected_execution_mode = execution_modes[0]
    selected_model = str(submitted.get("model") or "")
    submitted_provider = str(submitted.get("provider") or "")
    selected_provider = submitted_provider or _derive_provider_from_model(selected_model, engine=selected_engine)
    if not selected_provider:
        selected_provider = ENGINE_DEFAULT_PROVIDER.get(selected_engine, "")
    submitted_runtime_options = submitted.get("runtime_options", {})
    if not isinstance(submitted_runtime_options, dict):
        submitted_runtime_options = {}
    submitted_runtime_options = dict(submitted_runtime_options)
    submitted_runtime_options["hard_timeout_seconds"] = _resolve_hard_timeout_form_value(
        submitted_runtime_options=submitted_runtime_options,
        skill=skill,
        service_runtime_defaults=service_runtime_defaults,
    )
    return {
        "skill": skill,
        "schemas": schemas,
        "errors": errors,
        "run_source": run_source,
        "form_action": form_action,
        "inline_fields": input_fields["inline_fields"],
        "file_fields": input_fields["file_fields"],
        "parameter_fields": parameter_fields,
        "engines": engines,
        "engine_models_by_engine": engine_models_by_engine,
        "execution_modes": execution_modes,
        "selected_engine": selected_engine,
        "selected_provider": selected_provider,
        "selected_execution_mode": selected_execution_mode,
        "selected_model": selected_model,
        "submitted_runtime_options": submitted_runtime_options,
        "submitted_input": submitted.get("input", {}),
        "submitted_parameter": submitted.get("parameter", {}),
    }


def _extract_input_fields(schema: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    inline_fields: list[dict[str, Any]] = []
    file_fields: list[dict[str, Any]] = []
    required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    for name, raw_field in properties.items():
        if not isinstance(name, str):
            continue
        field = _build_field_meta(name, raw_field, required)
        source = field.get("source", "file")
        if source == "inline":
            inline_fields.append(field)
        else:
            file_fields.append(field)
    return {"inline_fields": inline_fields, "file_fields": file_fields}


def _extract_object_fields(schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return []
    fields: list[dict[str, Any]] = []
    for name, raw_field in properties.items():
        if not isinstance(name, str):
            continue
        fields.append(_build_field_meta(name, raw_field, required, default_source="inline"))
    return fields


def _build_field_meta(
    name: str,
    raw_field: Any,
    required: set[str],
    *,
    default_source: str = "file",
) -> dict[str, Any]:
    if isinstance(raw_field, dict):
        field_type = str(raw_field.get("type", "string"))
        source = str(raw_field.get("x-input-source", default_source))
        description = str(raw_field.get("description", "") or "")
    else:
        field_type = "string"
        source = default_source
        description = ""
    if source not in {"inline", "file"}:
        source = default_source
    return {
        "name": name,
        "type": field_type,
        "required": name in required,
        "description": description,
        "source": source,
    }


def _resolve_engine(selected: str, detail: Mapping[str, Any]) -> str:
    engines = _extract_engines(detail)
    if selected and selected in engines:
        return selected
    if engines:
        return engines[0]
    return "codex"


def _extract_execution_modes(detail: Mapping[str, Any]) -> list[str]:
    raw_modes = detail.get("execution_modes", [])
    if not isinstance(raw_modes, list):
        return ["auto"]
    modes: list[str] = []
    for item in raw_modes:
        if isinstance(item, str):
            value = item.strip()
            if value:
                modes.append(value)
    if not modes:
        return ["auto"]
    return list(dict.fromkeys(modes))


def _normalize_home_skills_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        skill_id = _coerce_non_empty_str(row.get("id"), "")
        if not skill_id:
            continue
        display_name = _coerce_non_empty_str(row.get("name"), skill_id)
        version = _coerce_non_empty_str(row.get("version"), "-")
        engines = _normalize_str_list(row.get("effective_engines")) or _normalize_str_list(row.get("engines"))
        health = _normalize_health_indicator(row.get("health"))
        normalized.append(
            {
                "id": skill_id,
                "display_name": display_name,
                "raw_name": skill_id,
                "version": version,
                "engines": engines,
                "execution_modes": _extract_execution_modes(row),
                "health_level": health["level"],
                "health_i18n_key": health["i18n_key"],
                "health_fallback": health["fallback"],
            }
        )
    return normalized


def _normalize_health_indicator(raw: Any) -> dict[str, str | None]:
    text = raw.strip() if isinstance(raw, str) else ""
    normalized = text.lower()
    yellow_states = {"unknown", "pending", "degraded", "warning"}
    red_states = {"error", "unhealthy", "failed", "offline"}
    if normalized == "healthy":
        return {
            "level": "healthy",
            "i18n_key": "client.index_health_healthy",
            "fallback": text or "healthy",
        }
    if normalized in yellow_states:
        return {
            "level": "warning",
            "i18n_key": f"client.index_health_{normalized}",
            "fallback": text or normalized,
        }
    if normalized in red_states:
        return {
            "level": "error",
            "i18n_key": f"client.index_health_{normalized}",
            "fallback": text or normalized,
        }
    if text:
        return {"level": "warning", "i18n_key": None, "fallback": text}
    return {
        "level": "warning",
        "i18n_key": "client.index_health_unknown",
        "fallback": "unknown",
    }


def _resolve_execution_mode(selected: str, detail: Mapping[str, Any]) -> tuple[str, str | None]:
    allowed = _extract_execution_modes(detail)
    if selected and selected in allowed:
        return selected, None
    if not selected:
        return allowed[0], None
    return selected, f"execution_mode '{selected}' is not allowed for this skill"


def _resolve_model(
    *,
    selected: str,
    allowed_models: list[str],
) -> tuple[str, str | None]:
    if not selected:
        return "", None
    if not allowed_models:
        return selected, None
    if selected in allowed_models:
        return selected, None
    return selected, f"model '{selected}' is not available for selected engine"


def _extract_engines(detail: Mapping[str, Any]) -> list[str]:
    engines_obj = detail.get("effective_engines")
    if not isinstance(engines_obj, list) or not engines_obj:
        engines_obj = detail.get("engines", [])
    if not isinstance(engines_obj, list):
        return []
    engines: list[str] = []
    for engine in engines_obj:
        if isinstance(engine, str):
            value = engine.strip()
            if value:
                engines.append(value)
    return list(dict.fromkeys(engines))


def _extract_management_engine_names(payload: Mapping[str, Any]) -> list[str]:
    rows = payload.get("engines")
    if not isinstance(rows, list):
        return []
    names: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            value = row.get("engine")
            if isinstance(value, str):
                name = value.strip()
                if name:
                    names.append(name)
    return list(dict.fromkeys(names))


def _extract_skill_runtime_default_options(detail: Mapping[str, Any]) -> dict[str, Any]:
    runtime_obj = detail.get("runtime")
    if not isinstance(runtime_obj, Mapping):
        return {}
    default_options_obj = runtime_obj.get("default_options")
    if not isinstance(default_options_obj, Mapping):
        return {}
    return {
        str(key): value
        for key, value in default_options_obj.items()
        if isinstance(key, str)
    }


def _resolve_hard_timeout_form_value(
    *,
    submitted_runtime_options: Mapping[str, Any],
    skill: Mapping[str, Any],
    service_runtime_defaults: Mapping[str, Any],
) -> str:
    raw_submitted = submitted_runtime_options.get("hard_timeout_seconds")
    if isinstance(raw_submitted, str):
        submitted_text = raw_submitted.strip()
        if submitted_text:
            return submitted_text
    elif isinstance(raw_submitted, int):
        return str(raw_submitted)

    skill_default = _coerce_non_negative_int(
        _extract_skill_runtime_default_options(skill).get("hard_timeout_seconds")
    )
    if skill_default is not None:
        return str(skill_default)

    service_default = _coerce_non_negative_int(service_runtime_defaults.get("hard_timeout_seconds"))
    if service_default is not None:
        return str(service_default)
    return ""


def _extract_engine_model_ids(
    engine_models_by_engine: dict[str, list[dict[str, Any]]],
    engine: str,
) -> list[str]:
    rows = engine_models_by_engine.get(engine, [])
    model_ids: list[str] = []
    for row in rows:
        value = row.get("id")
        if isinstance(value, str) and value.strip():
            model_ids.append(value.strip())
    return list(dict.fromkeys(model_ids))


def _derive_provider_from_model(model: str, *, engine: str) -> str:
    if engine != "opencode":
        return ENGINE_DEFAULT_PROVIDER.get(engine, "")
    if not model or "/" not in model:
        return ""
    provider = model.split("/", 1)[0].strip()
    return provider


def _collect_submitted_runtime_options(run_form: Mapping[str, Any]) -> dict[str, Any]:
    submitted: dict[str, Any] = {}
    for key in RUNTIME_BOOL_OPTIONS:
        submitted[key] = bool(run_form.get(f"runtime__{key}"))
    for key in RUNTIME_TIMEOUT_OPTIONS:
        submitted[key] = str(run_form.get(f"runtime__{key}", "") or "").strip()
    return submitted


def _build_runtime_options(
    *,
    execution_mode: str,
    submitted: dict[str, Any],
    run_source: RunSource,
) -> tuple[dict[str, Any], list[str]]:
    _ = run_source
    options: dict[str, Any] = {"execution_mode": execution_mode}
    errors: list[str] = []
    if bool(submitted.get("no_cache")):
        options["no_cache"] = True
    raw_hard_timeout = submitted.get("hard_timeout_seconds")
    if not isinstance(raw_hard_timeout, str) or not raw_hard_timeout.strip():
        errors.append("hard_timeout_seconds must be a non-negative integer")
    else:
        hard_timeout = _coerce_non_negative_int(raw_hard_timeout)
        if hard_timeout is None:
            errors.append("hard_timeout_seconds must be a non-negative integer")
        else:
            options["hard_timeout_seconds"] = hard_timeout
    if execution_mode == "interactive":
        interactive_auto_reply = bool(submitted.get("interactive_auto_reply"))
        options["interactive_auto_reply"] = interactive_auto_reply
        raw_value = submitted.get("interactive_reply_timeout_sec")
        if interactive_auto_reply:
            if not isinstance(raw_value, str) or not raw_value.strip():
                errors.append("interactive_reply_timeout_sec must be a non-negative integer")
            else:
                try:
                    parsed = int(raw_value.strip())
                except ValueError:
                    errors.append("interactive_reply_timeout_sec must be a non-negative integer")
                else:
                    if parsed < 0:
                        errors.append("interactive_reply_timeout_sec must be a non-negative integer")
                    else:
                        options["interactive_reply_timeout_sec"] = parsed
    return options, errors


def _collect_scalar_values(
    *,
    run_form: Mapping[str, Any],
    field_prefix: str,
    fields: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    values: dict[str, Any] = {}
    errors: list[str] = []
    for field in fields:
        key = str(field.get("name", ""))
        if not key:
            continue
        raw = run_form.get(f"{field_prefix}{key}", "")
        raw_text = str(raw) if raw is not None else ""
        if not raw_text.strip():
            if bool(field.get("required")):
                errors.append(f"{key} is required")
            continue
        try:
            values[key] = _coerce_scalar_value(raw_text, str(field.get("type", "string")))
        except ValueError as exc:
            errors.append(f"{key}: {exc}")
    return values, errors


async def _collect_file_values(
    *,
    run_form: Mapping[str, Any],
    file_fields: list[dict[str, Any]],
) -> tuple[dict[str, bytes], dict[str, str], list[str]]:
    files: dict[str, bytes] = {}
    file_inputs: dict[str, str] = {}
    errors: list[str] = []
    for field in file_fields:
        key = str(field.get("name", ""))
        if not key:
            continue
        upload = run_form.get(f"file__{key}")
        if upload is None or not hasattr(upload, "read"):
            if bool(field.get("required")):
                errors.append(f"{key} file is required")
            continue
        filename = str(getattr(upload, "filename", "") or "")
        if not filename:
            if bool(field.get("required")):
                errors.append(f"{key} file is required")
            continue
        body = await upload.read()
        if not body and bool(field.get("required")):
            errors.append(f"{key} file is empty")
            continue
        safe_filename = PurePosixPath(filename.replace("\\", "/")).name.strip()
        if not safe_filename:
            if bool(field.get("required")):
                errors.append(f"{key} file has invalid name")
            continue
        relative_path = f"{key}/{safe_filename}"
        files[relative_path] = body
        file_inputs[key] = relative_path
    return files, file_inputs, errors


def _coerce_scalar_value(raw: str, field_type: str) -> Any:
    if field_type == "integer":
        return int(raw)
    if field_type == "number":
        return float(raw)
    if field_type == "boolean":
        lowered = raw.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise ValueError("must be true/false")
    if field_type in {"object", "array"}:
        parsed = json.loads(raw)
        if field_type == "object" and not isinstance(parsed, dict):
            raise ValueError("must be a JSON object")
        if field_type == "array" and not isinstance(parsed, list):
            raise ValueError("must be a JSON array")
        return parsed
    return raw


def _build_upload_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, body in sorted(files.items()):
            archive.writestr(key, body)
    return buffer.getvalue()


def _as_schema_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _normalize_bundle_request_path(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("invalid path")
    for part in candidate.parts:
        if part in {"", ".", ".."}:
            raise ValueError("invalid path")
    normalized = candidate.as_posix().rstrip("/")
    if not normalized:
        raise ValueError("invalid path")
    return normalized
