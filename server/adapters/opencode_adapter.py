import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

from .base import (
    EngineAdapter,
    ProcessExecutionResult,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
)
from ..models import (
    AdapterTurnResult,
    EngineSessionHandle,
    EngineSessionHandleType,
    SkillManifest,
)
from ..services.agent_cli_manager import AgentCliManager
from ..services.engine_command_profile import engine_command_profile, merge_cli_args
from ..services.schema_validator import schema_validator
from ..services.skill_patcher import skill_patcher
from ..services.runtime_parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
from ..services.opencode_model_catalog import opencode_model_catalog

logger = logging.getLogger(__name__)


class OpencodeAdapter(EngineAdapter):
    def __init__(self) -> None:
        self.agent_manager = AgentCliManager()

    def _load_json_config(self, config_path: Path, *, label: str) -> Dict[str, Any]:
        if not config_path.exists():
            return {}
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load %s config: %s", label, config_path, exc_info=True)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _deep_merge_dicts(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge_dicts(base[key], value)
            else:
                base[key] = value
        return base

    def _mode_permission_overlay(self, options: Dict[str, Any]) -> Dict[str, Any]:
        execution_mode = self._resolve_execution_mode(options)
        question_mode = "allow" if execution_mode == "interactive" else "deny"
        return {"permission": {"question": question_mode}}

    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        layers: list[Dict[str, Any]] = []

        engine_default_path = Path(__file__).parent.parent / "assets" / "configs" / "opencode" / "default.json"
        layers.append(self._load_json_config(engine_default_path, label="opencode default"))

        skill_defaults: Dict[str, Any] = {}
        if skill.path:
            candidate = skill.path / "assets" / "opencode_config.json"
            if candidate.exists():
                skill_defaults = self._load_json_config(candidate, label="opencode skill default")
        layers.append(skill_defaults)

        runtime_override: Dict[str, Any] = {}
        if isinstance(options.get("opencode_config"), dict):
            runtime_override = options["opencode_config"]
        layers.append(runtime_override)

        enforced_path = Path(__file__).parent.parent / "assets" / "configs" / "opencode" / "enforced.json"
        layers.append(self._load_json_config(enforced_path, label="opencode enforced"))

        layers.append(self._mode_permission_overlay(options))

        merged: Dict[str, Any] = {}
        for layer in layers:
            if isinstance(layer, dict):
                self._deep_merge_dicts(merged, layer)
        config_path = run_dir / "opencode.json"
        config_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config_path

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        _ = config_path
        opencode_ws_dir = run_dir / ".opencode"
        skills_target_dir = opencode_ws_dir / "skills" / skill.id
        if skill.path:
            if skills_target_dir.exists():
                shutil.rmtree(skills_target_dir)
            try:
                shutil.copytree(skill.path, skills_target_dir)
                logger.info("Installed skill %s to %s", skill.id, skills_target_dir)
            except Exception:
                logger.exception("Failed to copy skill into opencode workspace")
        output_schema_relpath = (
            str(skill.schemas.get("output"))
            if isinstance(skill.schemas, dict) and isinstance(skill.schemas.get("output"), str)
            else None
        )
        output_schema = skill_patcher.load_output_schema(
            skill_path=skill.path,
            output_schema_relpath=output_schema_relpath,
        )
        skill_patcher.patch_skill_md(
            skills_target_dir,
            skill.artifacts or [],
            execution_mode=self._resolve_execution_mode(options),
            output_schema=output_schema,
        )
        return skills_target_dir

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: Dict[str, Any]) -> str:
        input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir, input_data)
        if missing_required:
            raise ValueError(f"Missing required input files: {', '.join(missing_required)}")
        parameter_ctx = schema_validator.build_parameter_context(skill, input_data)
        prompt_template_str = ""
        if skill.entrypoint and "prompts" in skill.entrypoint and "opencode" in skill.entrypoint["prompts"]:
            prompt_template_str = skill.entrypoint["prompts"]["opencode"]
        else:
            template_path = Path(__file__).parent.parent / "assets" / "templates" / "opencode_default.j2"
            if template_path.exists():
                prompt_template_str = template_path.read_text(encoding="utf-8")
            else:
                prompt_template_str = '{{ input_prompt }}'
        template = Template(prompt_template_str)
        main_prompt = parameter_ctx.get("prompt", f"Execute skill {skill.id}")
        return template.render(
            skill=skill,
            input_prompt=main_prompt,
            input=input_ctx,
            parameter=parameter_ctx,
            run_dir=str(run_dir),
        )

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        _ = skill
        env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())

        resume_handle = options.get("__resume_session_handle")
        if isinstance(resume_handle, dict):
            command = self.build_resume_command(
                prompt=prompt,
                options=options,
                session_handle=EngineSessionHandle.model_validate(resume_handle),
            )
        else:
            command = self.build_start_command(prompt=prompt, options=options)

        logger.info("Executing opencode command: %s", " ".join(command))
        proc = await self._create_subprocess(
            *command,
            cwd=run_dir,
            env=env,
        )
        try:
            return await self._capture_process_output(proc, run_dir, options, "Opencode")
        finally:
            opencode_model_catalog.request_refresh_async(reason="post_run")

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="opencode", action=action)

    def _resolve_opencode_command(self) -> Path:
        command = self.agent_manager.resolve_engine_command("opencode")
        if command is None:
            raise RuntimeError("Opencode CLI not found in managed prefix")
        return command

    def _model_args(self, options: Dict[str, Any]) -> list[str]:
        model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            return ["--model", model_obj.strip()]
        return []

    def _extract_passthrough_options(
        self,
        passthrough_args: list[str],
        *,
        blocked_option_keys: set[str] | None = None,
    ) -> list[str]:
        blocked = blocked_option_keys or set()
        normalized_blocked = {key.strip() for key in blocked if key.strip()}
        parsed: list[str] = []
        idx = 0
        while idx < len(passthrough_args):
            token = passthrough_args[idx]
            if not isinstance(token, str):
                idx += 1
                continue
            current = token.strip()
            if not current.startswith("-"):
                idx += 1
                continue
            key = current.split("=", 1)[0] if "=" in current else current
            if key in normalized_blocked:
                if "=" not in current and idx + 1 < len(passthrough_args):
                    next_token = passthrough_args[idx + 1]
                    if isinstance(next_token, str) and not next_token.strip().startswith("-"):
                        idx += 2
                        continue
                idx += 1
                continue
            parsed.append(current)
            if "=" not in current and idx + 1 < len(passthrough_args):
                next_token = passthrough_args[idx + 1]
                if isinstance(next_token, str):
                    next_clean = next_token.strip()
                    if next_clean and not next_clean.startswith("-"):
                        parsed.append(next_clean)
                        idx += 2
                        continue
            idx += 1
        return parsed

    def _extract_text_event(self, payload: Dict[str, Any]) -> str | None:
        payload_type = payload.get("type")
        if payload_type != "text":
            return None
        part = payload.get("part")
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text
        return None

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        last_text: str = ""
        for line in raw_stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            extracted = self._extract_text_event(payload)
            if extracted:
                last_text = extracted
        source_text = last_text or raw_stdout
        result, repair_level = self._parse_json_with_deterministic_repair(source_text)
        if result is not None:
            return self._build_turn_result_from_payload(result, repair_level)
        logger.warning("Failed to parse opencode output")
        return self._turn_error(message="failed to parse opencode output")

    def extract_session_handle(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        session_id: str | None = None
        for line in raw_stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise RuntimeError("SESSION_RESUME_FAILED: invalid opencode json stream") from exc
            if isinstance(payload, dict):
                session_id = find_session_id(payload)
            if session_id:
                break
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: missing opencode session id")
        return EngineSessionHandle(
            engine="opencode",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=session_id,
            created_at_turn=turn_index,
        )

    def _build_run_command_with_defaults(
        self,
        *,
        prompt: str,
        defaults: list[str],
        explicit_flags: list[str],
        session_id: str | None = None,
        options: Dict[str, Any],
    ) -> list[str]:
        merged_flags = merge_cli_args(defaults, explicit_flags)
        command: list[str] = [str(self._resolve_opencode_command()), "run"]
        if session_id is not None:
            command.append(f"--session={session_id}")
        command.extend(merged_flags)
        command.extend(self._model_args(options))
        command.append(prompt)
        return command

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        executable = str(self._resolve_opencode_command())
        if passthrough_args is not None:
            return [executable, *passthrough_args]
        defaults = self._resolve_profile_flags(action="start", use_profile_defaults=use_profile_defaults)
        return self._build_run_command_with_defaults(
            prompt=prompt,
            defaults=defaults,
            explicit_flags=[],
            options=options,
        )

    def build_resume_command(
        self,
        prompt: str,
        options: Dict[str, Any],
        session_handle: EngineSessionHandle,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty opencode session id")
        if passthrough_args is not None:
            flags = self._extract_passthrough_options(
                [str(token) for token in passthrough_args],
                blocked_option_keys={"--session"},
            )
            return self._build_run_command_with_defaults(
                prompt=prompt,
                defaults=[],
                explicit_flags=flags,
                session_id=session_id,
                options=options,
            )
        defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=use_profile_defaults)
        return self._build_run_command_with_defaults(
            prompt=prompt,
            defaults=defaults,
            explicit_flags=[],
            session_id=session_id,
            options=options,
        )

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        records, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)
        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []

        def _consume(parsed_rows: list[dict[str, Any]]) -> None:
            nonlocal session_id
            for row in parsed_rows:
                payload = row["payload"]
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if not isinstance(payload, dict):
                    continue
                text = self._extract_text_event(payload)
                if isinstance(text, str) and text.strip():
                    assistant_messages.append(
                        {
                            "text": text,
                            "raw_ref": {
                                "stream": row["stream"],
                                "byte_from": row["byte_from"],
                                "byte_to": row["byte_to"],
                            },
                        }
                    )

        _consume(records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _consume(pty_records)
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")
        return {
            "parser": "opencode_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
