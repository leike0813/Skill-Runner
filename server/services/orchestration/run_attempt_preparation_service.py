from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from server.models import EngineInteractiveProfile, SkillManifest
from server.runtime.session.timeout import resolve_interactive_reply_timeout
from server.services.engine_management.engine_policy import apply_engine_policy_to_manifest
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts
from server.services.orchestration.run_folder_git_initializer import run_folder_git_initializer
from server.services.orchestration.run_output_schema_service import run_output_schema_service
from server.services.orchestration.run_skill_materialization_service import run_folder_bootstrapper
from server.services.platform.schema_validator import schema_validator
from server.services.skill.skill_asset_resolver import resolve_schema_asset
from server.services.skill.skill_registry import skill_registry
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.config import config
from pydantic import ValidationError

if TYPE_CHECKING:
    from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


@dataclass
class RunAttemptContext:
    request: RunJobRequest
    run_dir: Path
    request_record: dict[str, Any] | None
    request_id: str | None
    execution_mode: str
    conversation_mode: str
    session_capable: bool
    is_interactive: bool
    interactive_auto_reply: bool
    can_wait_for_user: bool
    can_persist_waiting_user: bool
    interactive_profile: EngineInteractiveProfile | None
    attempt_number: int
    skill: SkillManifest
    adapter: Any
    input_data: dict[str, dict[str, Any]]
    run_options: dict[str, Any]
    custom_provider_model: str | None


def resolve_interactive_auto_reply(
    *,
    options: dict[str, Any],
    request_record: dict[str, Any],
) -> bool:
    if "interactive_auto_reply" in options:
        value = options.get("interactive_auto_reply")
        if isinstance(value, bool):
            return value
    runtime_options = request_record.get(
        "effective_runtime_options",
        request_record.get("runtime_options", {}),
    )
    value = runtime_options.get("interactive_auto_reply", False)
    return bool(value)


def resolve_session_timeout_seconds(options: dict[str, Any]) -> int:
    return resolve_interactive_reply_timeout(
        options,
        default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
    ).value


async def resolve_attempt_number(
    *,
    run_store_backend: Any,
    request_id: str | None,
    is_interactive: bool,
) -> int:
    if not request_id or not is_interactive:
        return 1
    interaction_count = await run_store_backend.get_interaction_count(request_id)
    return max(1, int(interaction_count) + 1)


def load_skill_from_run_dir(
    *,
    run_dir: Path,
    skill_id: str,
    engine_name: str,
) -> SkillManifest | None:
    workspace_subdir = ".codex"
    profile_path = (
        Path(__file__).resolve().parents[2]
        / "engines"
        / engine_name
        / "adapter"
        / "adapter_profile.json"
    )
    try:
        profile = load_adapter_profile(engine_name, profile_path)
        workspace_subdir = profile.attempt_workspace.workspace_subdir
    except RuntimeError:
        pass
    skill_dir = run_dir / workspace_subdir / "skills" / skill_id
    runner_path = skill_dir / "assets" / "runner.json"
    if not runner_path.exists() or not runner_path.is_file():
        return None
    try:
        data = json.loads(runner_path.read_text(encoding="utf-8"))
        data = infer_manifest_artifacts(data, skill_dir)
        apply_engine_policy_to_manifest(data)
        return SkillManifest(**data, path=skill_dir)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
        return None


async def inject_interactive_resume_context(
    *,
    interaction_service: Any,
    run_store_backend: Any,
    audit_service: Any,
    request_id: str,
    profile: EngineInteractiveProfile,
    options: dict[str, Any],
    run_dir: Path,
    resolve_attempt_number: Callable[..., Any],
    build_reply_prompt: Callable[[Any], str],
) -> None:
    await interaction_service.inject_interactive_resume_context(
        request_id=request_id,
        profile=profile,
        options=options,
        run_dir=run_dir,
        run_store_backend=run_store_backend,
        append_internal_schema_warning=audit_service.append_internal_schema_warning,
        resolve_attempt_number=resolve_attempt_number,
        build_reply_prompt=build_reply_prompt,
    )


class RunAttemptPreparationService:
    async def prepare(
        self,
        *,
        orchestrator: Any,
        request: RunJobRequest,
        run_dir: Path,
        request_record: dict[str, Any] | None,
        request_id: str | None,
        execution_mode: str,
        conversation_mode: str,
        session_capable: bool,
        is_interactive: bool,
        interactive_auto_reply: bool,
        can_wait_for_user: bool,
        can_persist_waiting_user: bool,
        interactive_profile: EngineInteractiveProfile | None,
        attempt_number: int,
        resolve_custom_provider_model: Callable[..., str | None],
        run_store_backend: Any | None = None,
        interaction_service: Any | None = None,
        audit_service: Any | None = None,
        resolve_attempt_number: Callable[..., Any] | None = None,
        build_reply_prompt: Callable[[Any], str] | None = None,
    ) -> RunAttemptContext:
        skill = request.skill_override
        if skill is None:
            skill = run_folder_bootstrapper.load_from_snapshot(
                run_dir=run_dir,
                skill_id=request.skill_id,
                engine_name=request.engine_name,
            )
        if skill is None:
            skill = skill_registry.get_skill(request.skill_id)
        if skill is None and is_interactive:
            skill = load_skill_from_run_dir(
                run_dir=run_dir,
                skill_id=request.skill_id,
                engine_name=request.engine_name,
            )
        if not skill:
            raise ValueError(f"Skill {request.skill_id} not found during execution")
        if not all(
            resolve_schema_asset(skill, key).path is not None
            for key in ("input", "parameter", "output")
        ):
            raise ValueError("Schema missing: input/parameter/output must be defined")

        adapter = orchestrator.adapters.get(request.engine_name)
        if not adapter:
            raise ValueError(f"Engine {request.engine_name} not supported")

        input_data = {
            "input": dict((request_record or {}).get("input") or {}),
            "parameter": dict((request_record or {}).get("parameter") or {}),
        }
        real_params = input_data.get("parameter", {})
        input_errors: list[str] = []
        if resolve_schema_asset(skill, "parameter").path is not None:
            input_errors.extend(
                schema_validator.validate_schema(skill, real_params, "parameter")
            )
        if resolve_schema_asset(skill, "input").path is not None:
            input_errors.extend(
                schema_validator.validate_input_for_execution(skill, run_dir, input_data)
            )
        if input_errors:
            raise ValueError(f"Input validation failed: {str(input_errors)}")

        run_folder_git_initializer.ensure_git_repo(run_dir)
        run_options = dict(request.options)
        run_options["__run_id"] = request.run_id
        run_options["__attempt_number"] = attempt_number
        if request_id:
            run_options["__request_id"] = request_id
        run_options["__engine_name"] = request.engine_name
        run_option_fields = run_output_schema_service.build_run_option_fields(run_dir=run_dir)
        if not run_option_fields:
            run_output_schema_service.materialize(
                skill=skill,
                execution_mode=execution_mode,
                run_dir=run_dir,
            )
            run_option_fields = run_output_schema_service.build_run_option_fields(run_dir=run_dir)
        run_options.update(run_option_fields)
        if is_interactive and request_id and interactive_profile:
            await inject_interactive_resume_context(
                interaction_service=interaction_service or orchestrator.interaction_service,
                run_store_backend=run_store_backend or orchestrator._run_store_backend(),
                audit_service=audit_service or orchestrator.audit_service,
                request_id=request_id,
                profile=interactive_profile,
                options=run_options,
                run_dir=run_dir,
                resolve_attempt_number=resolve_attempt_number or orchestrator._resolve_attempt_number,
                build_reply_prompt=build_reply_prompt or orchestrator._build_reply_prompt,
            )

        custom_provider_model = resolve_custom_provider_model(
            engine_name=request.engine_name,
            options=request.options,
            request_record=request_record,
        )
        return RunAttemptContext(
            request=request,
            run_dir=run_dir,
            request_record=request_record if isinstance(request_record, dict) else None,
            request_id=request_id if isinstance(request_id, str) else None,
            execution_mode=execution_mode,
            conversation_mode=conversation_mode,
            session_capable=session_capable,
            is_interactive=is_interactive,
            interactive_auto_reply=interactive_auto_reply,
            can_wait_for_user=can_wait_for_user,
            can_persist_waiting_user=can_persist_waiting_user,
            interactive_profile=interactive_profile,
            attempt_number=attempt_number,
            skill=skill,
            adapter=adapter,
            input_data=input_data,
            run_options=run_options,
            custom_provider_model=custom_provider_model,
        )
