from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse  # type: ignore[import-not-found]
from fastapi.templating import Jinja2Templates  # type: ignore[import-not-found]

from .backend import BackendApiError, BackendClient, HttpBackendClient
from .config import E2EClientSettings
from .recording import RecordingStore


TEMPLATE_ROOT = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))

router = APIRouter(tags=["e2e-client"])

RUNTIME_BOOL_OPTIONS = ("verbose", "no_cache", "debug", "debug_keep_temp")
RUNTIME_TIMEOUT_OPTIONS = (
    "session_timeout_sec",
    "interactive_wait_timeout_sec",
    "hard_wait_timeout_sec",
    "wait_timeout_sec",
)
PREVIEW_MAX_BYTES = 256 * 1024
TEXT_DECODE_CANDIDATES = (
    "utf-8",
    "utf-8-sig",
    "gb18030",
    "big5",
)


def get_settings(request: Request) -> E2EClientSettings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, E2EClientSettings):
        raise RuntimeError("E2E client settings are not configured")
    return settings


def get_backend_client(
    settings: E2EClientSettings = Depends(get_settings),
) -> BackendClient:
    return HttpBackendClient(settings.backend_base_url)


def get_recording_store(request: Request) -> RecordingStore:
    store = getattr(request.app.state, "recording_store", None)
    if not isinstance(store, RecordingStore):
        raise RuntimeError("Recording store is not configured")
    return store


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        payload = await backend.list_skills()
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "skills": skills,
        },
    )


@router.get("/skills/{skill_id}/run", response_class=HTMLResponse)
async def run_form_page(
    request: Request,
    skill_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    detail, schemas = await _load_skill_bundle(backend, skill_id)
    engine_models_by_engine = await _load_engine_models(backend, detail)
    return templates.TemplateResponse(
        request=request,
        name="run_form.html",
        context=_build_run_form_context(
            skill=detail,
            schemas=schemas,
            engine_models_by_engine=engine_models_by_engine,
            errors=[],
            submitted={
                "engine": "",
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
    recordings: RecordingStore = Depends(get_recording_store),
):
    detail, schemas = await _load_skill_bundle(backend, skill_id)
    engine_models_by_engine = await _load_engine_models(backend, detail)
    run_form = await request.form()
    submitted_engine = str(run_form.get("engine", "") or "")
    submitted_execution_mode = str(run_form.get("execution_mode", "") or "")
    submitted_model = str(run_form.get("model", "") or "").strip()
    submitted_runtime_options = _collect_submitted_runtime_options(run_form)
    engine = _resolve_engine(submitted_engine, detail)
    execution_mode, mode_error = _resolve_execution_mode(submitted_execution_mode, detail)
    selected_model, model_error = _resolve_model(
        selected=submitted_model,
        allowed_models=_extract_engine_model_ids(engine_models_by_engine, engine),
    )
    runtime_options, runtime_errors = _build_runtime_options(
        execution_mode=execution_mode,
        submitted=submitted_runtime_options,
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
    uploaded_files, file_errors = await _collect_file_values(
        run_form=run_form,
        file_fields=input_fields["file_fields"],
    )

    errors = input_errors + parameter_errors + file_errors + runtime_errors
    if mode_error:
        errors.append(mode_error)
    if model_error:
        errors.append(model_error)
    if errors:
        return templates.TemplateResponse(
            request=request,
            name="run_form.html",
            context=_build_run_form_context(
                skill=detail,
                schemas=schemas,
                engine_models_by_engine=engine_models_by_engine,
                errors=errors,
                submitted={
                    "engine": engine,
                    "execution_mode": execution_mode if not mode_error else submitted_execution_mode,
                    "model": selected_model if not model_error else submitted_model,
                    "runtime_options": submitted_runtime_options,
                    "input": inline_input,
                    "parameter": parameter_input,
                },
            ),
            status_code=400,
        )

    create_payload = {
        "skill_id": skill_id,
        "engine": engine,
        "input": inline_input,
        "parameter": parameter_input,
        "runtime_options": runtime_options,
    }
    if selected_model:
        create_payload["model"] = selected_model

    try:
        create_response = await backend.create_run(create_payload)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    request_id_raw = create_response.get("request_id")
    if not isinstance(request_id_raw, str) or not request_id_raw:
        raise HTTPException(status_code=502, detail="Missing request_id in backend response")
    request_id = request_id_raw
    recordings.append_step(
        request_id,
        action="create_run",
        request_summary=create_payload,
        response_summary=create_response,
    )

    if uploaded_files:
        zip_bytes = _build_upload_zip(uploaded_files)
        try:
            upload_response = await backend.upload_run_file(request_id, zip_bytes)
        except BackendApiError as exc:
            recordings.append_step(
                request_id,
                action="upload",
                request_summary={"files": sorted(uploaded_files.keys())},
                response_summary={"detail": exc.detail},
                status="error",
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        recordings.append_step(
            request_id,
            action="upload",
            request_summary={"files": sorted(uploaded_files.keys())},
            response_summary=upload_response,
        )

    return RedirectResponse(
        url=f"/runs/{request_id}",
        status_code=303,
    )


@router.get("/runs/{request_id}", response_class=HTMLResponse)
async def run_observe_page(
    request: Request,
    request_id: str,
):
    return templates.TemplateResponse(
        request=request,
        name="run_observe.html",
        context={"request_id": request_id},
    )


@router.get("/runs", response_class=HTMLResponse)
async def list_runs_page(
    request: Request,
    backend: BackendClient = Depends(get_backend_client),
    recordings: RecordingStore = Depends(get_recording_store),
):
    rows = recordings.list_recordings()
    run_rows: list[dict[str, Any]] = []
    for row in rows:
        request_id = str(row.get("request_id") or "")
        summary = {
            "status": "unknown",
            "run_id": "-",
            "skill_id": "-",
            "engine": "-",
            "state_error": None,
        }
        if request_id:
            try:
                state = await backend.get_run_state(request_id)
            except BackendApiError as exc:
                summary["status"] = "unavailable"
                summary["state_error"] = str(exc.detail)
            else:
                summary = _summarize_run_state(state)
        run_rows.append(
            {
                "request_id": request_id,
                "updated_at": row.get("updated_at"),
                "step_count": row.get("step_count", 0),
                **summary,
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="runs.html",
        context={"rows": run_rows},
    )


@router.get("/runs/{request_id}/result", response_class=HTMLResponse)
async def run_result_page(
    request: Request,
    request_id: str,
    backend: BackendClient = Depends(get_backend_client),
    settings: E2EClientSettings = Depends(get_settings),
    recordings: RecordingStore = Depends(get_recording_store),
):
    try:
        result_payload = await backend.get_run_result(request_id)
        artifacts_payload = await backend.get_run_artifacts(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    bundle_entries: list[dict[str, Any]] = []
    bundle_error: str | None = None
    try:
        bundle_bytes = await backend.get_run_bundle(request_id)
        bundle_entries = _list_bundle_entries(bundle_bytes)
    except BackendApiError as exc:
        bundle_error = f"Unable to read bundle: {exc.detail}"
    except Exception:
        bundle_error = "Unable to parse bundle content"

    recordings.append_step(
        request_id,
        action="result_read",
        request_summary={"request_id": request_id},
        response_summary={
            "has_result": bool(result_payload.get("result")),
            "artifact_count": len(artifacts_payload.get("artifacts", [])),
        },
    )
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "request_id": request_id,
            "backend_base_url": settings.backend_base_url,
            "result_payload": result_payload,
            "artifacts_payload": artifacts_payload,
            "bundle_entries": bundle_entries,
            "bundle_error": bundle_error,
            "result_json": json.dumps(
                result_payload.get("result", {}),
                ensure_ascii=False,
                indent=2,
            ),
        },
    )


@router.get("/recordings", response_class=HTMLResponse)
async def list_recordings_page(
    request: Request,
):
    del request
    return RedirectResponse(
        url="/runs",
        status_code=307,
    )


@router.get("/recordings/{request_id}", response_class=HTMLResponse)
async def recording_detail_page(
    request: Request,
    request_id: str,
    recordings: RecordingStore = Depends(get_recording_store),
):
    try:
        payload = recordings.get_recording(request_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Recording not found")
    return templates.TemplateResponse(
        request=request,
        name="recording_detail.html",
        context={
            "request_id": request_id,
            "step_count": len(payload.get("steps", []))
            if isinstance(payload.get("steps"), list)
            else 0,
        },
    )


@router.get("/api/recordings/{request_id}")
async def get_recording_payload(
    request_id: str,
    recordings: RecordingStore = Depends(get_recording_store),
):
    try:
        return recordings.get_recording(request_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Recording not found")


@router.get("/api/runs/{request_id}")
async def get_run_state_api(
    request_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        return await backend.get_run_state(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/runs/{request_id}/pending")
async def get_run_pending_api(
    request_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        return await backend.get_run_pending(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/runs/{request_id}/bundle/entries")
async def get_run_bundle_entries_api(
    request_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        bundle_bytes = await backend.get_run_bundle(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    try:
        entries = _list_bundle_entries(bundle_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"request_id": request_id, "entries": entries}


@router.get("/api/runs/{request_id}/bundle/file")
async def get_run_bundle_file_api(
    request_id: str,
    path: str,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        bundle_bytes = await backend.get_run_bundle(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    try:
        preview = _build_bundle_file_preview(bundle_bytes, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except IsADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"request_id": request_id, "path": path, "preview": preview}


@router.get("/runs/{request_id}/bundle/view", response_class=HTMLResponse)
async def get_run_bundle_file_view(
    request: Request,
    request_id: str,
    path: str,
    backend: BackendClient = Depends(get_backend_client),
):
    try:
        bundle_bytes = await backend.get_run_bundle(request_id)
    except BackendApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    try:
        preview = _build_bundle_file_preview(bundle_bytes, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except IsADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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
    backend: BackendClient = Depends(get_backend_client),
    recordings: RecordingStore = Depends(get_recording_store),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Reply payload must be an object")
    try:
        reply = await backend.post_run_reply(request_id, payload)
    except BackendApiError as exc:
        recordings.append_step(
            request_id,
            action="reply",
            request_summary=payload,
            response_summary={"detail": exc.detail},
            status="error",
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    recordings.append_step(
        request_id,
        action="reply",
        request_summary=payload,
        response_summary=reply,
    )
    return reply


@router.get("/api/runs/{request_id}/events")
async def stream_run_events_api(
    request_id: str,
    backend: BackendClient = Depends(get_backend_client),
):
    async def _stream():
        try:
            async for chunk in backend.stream_run_events(request_id):
                yield chunk
        except BackendApiError as exc:
            payload = {"error": exc.detail, "status_code": exc.status_code}
            frame = f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield frame.encode("utf-8")

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


def _build_run_form_context(
    *,
    skill: dict[str, Any],
    schemas: dict[str, Any],
    engine_models_by_engine: dict[str, list[dict[str, Any]]],
    errors: list[str],
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
    submitted_runtime_options = submitted.get("runtime_options", {})
    if not isinstance(submitted_runtime_options, dict):
        submitted_runtime_options = {}
    return {
        "skill": skill,
        "schemas": schemas,
        "errors": errors,
        "inline_fields": input_fields["inline_fields"],
        "file_fields": input_fields["file_fields"],
        "parameter_fields": parameter_fields,
        "engines": engines,
        "engine_models_by_engine": engine_models_by_engine,
        "execution_modes": execution_modes,
        "selected_engine": selected_engine,
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


def _summarize_run_state(state: Mapping[str, Any]) -> dict[str, Any]:
    status = str(state.get("status") or "unknown")
    run_id = str(state.get("run_id") or "-")
    skill_id = str(state.get("skill_id") or "-")
    engine = str(state.get("engine") or "-")
    return {
        "status": status,
        "run_id": run_id,
        "skill_id": skill_id,
        "engine": engine,
        "state_error": None,
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


def _collect_submitted_runtime_options(run_form: Mapping[str, Any]) -> dict[str, Any]:
    submitted: dict[str, Any] = {}
    for key in RUNTIME_BOOL_OPTIONS:
        submitted[key] = bool(run_form.get(f"runtime__{key}"))
    mode = str(run_form.get("runtime__interactive_require_user_reply", "") or "").strip()
    submitted["interactive_require_user_reply"] = mode
    for key in RUNTIME_TIMEOUT_OPTIONS:
        submitted[key] = str(run_form.get(f"runtime__{key}", "") or "").strip()
    return submitted


def _build_runtime_options(
    *,
    execution_mode: str,
    submitted: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    options: dict[str, Any] = {"execution_mode": execution_mode}
    errors: list[str] = []
    for key in RUNTIME_BOOL_OPTIONS:
        if bool(submitted.get(key)):
            options[key] = True
    reply_mode = submitted.get("interactive_require_user_reply")
    if isinstance(reply_mode, str) and reply_mode:
        if reply_mode == "true":
            options["interactive_require_user_reply"] = True
        elif reply_mode == "false":
            options["interactive_require_user_reply"] = False
        else:
            errors.append("interactive_require_user_reply must be default/true/false")
    for key in RUNTIME_TIMEOUT_OPTIONS:
        raw_value = submitted.get(key)
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        try:
            parsed = int(raw_value.strip())
        except ValueError:
            errors.append(f"{key} must be a positive integer")
            continue
        if parsed <= 0:
            errors.append(f"{key} must be a positive integer")
            continue
        options[key] = parsed
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
) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
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
        files[key] = body
    return files, errors


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


def _list_bundle_entries(bundle_bytes: bytes) -> list[dict[str, Any]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(bundle_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("Bundle is not a valid zip archive") from exc
    with archive:
        file_sizes: dict[str, int] = {}
        dir_paths: set[str] = set()
        for info in archive.infolist():
            normalized = _normalize_zip_member_name(info.filename)
            if not normalized:
                continue
            if info.is_dir():
                dir_paths.add(normalized)
                continue
            file_sizes[normalized] = int(info.file_size)
            parent = PurePosixPath(normalized).parent
            while str(parent) not in {"", "."}:
                dir_paths.add(parent.as_posix())
                parent = parent.parent

    meta: dict[str, dict[str, Any]] = {}
    for path in sorted(dir_paths):
        meta[path] = {"is_dir": True, "size": None}
    for path, size in file_sizes.items():
        meta[path] = {"is_dir": False, "size": size}

    children: dict[str, list[str]] = {}
    for path in meta:
        parent_key = PurePosixPath(path).parent.as_posix()
        if parent_key == ".":
            parent_key = ""
        children.setdefault(parent_key, []).append(path)

    entries: list[dict[str, Any]] = []

    def _walk(parent: str, depth: int) -> None:
        for child in sorted(
            children.get(parent, []),
            key=lambda item: (
                not bool(meta[item]["is_dir"]),
                PurePosixPath(item).name.lower(),
            ),
        ):
            child_meta = meta[child]
            entries.append(
                {
                    "path": child,
                    "name": PurePosixPath(child).name,
                    "is_dir": bool(child_meta["is_dir"]),
                    "depth": depth,
                    "size": child_meta["size"],
                }
            )
            if bool(child_meta["is_dir"]):
                _walk(child, depth + 1)

    _walk("", 0)
    return entries


def _build_bundle_file_preview(bundle_bytes: bytes, relative_path: str) -> dict[str, Any]:
    normalized = _normalize_bundle_request_path(relative_path)
    try:
        archive = zipfile.ZipFile(io.BytesIO(bundle_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("Bundle is not a valid zip archive") from exc
    with archive:
        try:
            info = archive.getinfo(normalized)
        except KeyError as exc:
            raise FileNotFoundError("file not found in bundle") from exc
        if info.is_dir():
            raise IsADirectoryError("path points to a directory")
        size = int(info.file_size)
        if size > PREVIEW_MAX_BYTES:
            return {
                "mode": "too_large",
                "content": None,
                "size": size,
                "meta": "bundle file too large",
            }
        data = archive.read(normalized)
        if _is_binary_blob(data):
            return {
                "mode": "binary",
                "content": None,
                "size": size,
                "meta": "binary file in bundle",
            }
        content, encoding = _decode_text_blob(data)
        return {
            "mode": "text",
            "content": content,
            "size": size,
            "meta": f"{size} bytes, {encoding}",
        }


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


def _normalize_zip_member_name(raw_name: str) -> str | None:
    candidate = PurePosixPath(raw_name.replace("\\", "/"))
    if candidate.is_absolute():
        return None
    parts = candidate.parts
    if not parts:
        return None
    if any(part in {"", ".", ".."} for part in parts):
        return None
    normalized = candidate.as_posix().rstrip("/")
    return normalized or None


def _is_binary_blob(data: bytes) -> bool:
    sample = data[:4096]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    control_count = 0
    for byte in sample:
        if byte in {9, 10, 13}:
            continue
        if 32 <= byte <= 126:
            continue
        if byte >= 128:
            continue
        control_count += 1
    if control_count / len(sample) > 0.30:
        return True
    return False


def _decode_text_blob(data: bytes) -> tuple[str, str]:
    for encoding in TEXT_DECODE_CANDIDATES:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"
