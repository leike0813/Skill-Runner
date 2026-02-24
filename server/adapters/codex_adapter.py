import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from server.services.codex_config_manager import CodexConfigManager
from server.services.agent_cli_manager import AgentCliManager
from server.services.engine_command_profile import engine_command_profile, merge_cli_args
from server.services.runtime_parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

logger = logging.getLogger(__name__)

from .base import (
    EngineAdapter,
    ProcessExecutionResult,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
)
from ..models import AdapterTurnResult, EngineSessionHandle, EngineSessionHandleType, SkillManifest

RUNNER_ONLY_OPTION_KEYS = {
    "verbose",
    "no_cache",
    "debug",
    "debug_keep_temp",
    "execution_mode",
    "interactive_require_user_reply",
    "session_timeout_sec",
    "interactive_wait_timeout_sec",
    "hard_wait_timeout_sec",
    "wait_timeout_sec",
    "hard_timeout_seconds",
}

CODEX_CONFIG_PASSTHROUGH_KEYS = {
    "model",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "model_supports_reasoning_summaries",
}

class CodexAdapter(EngineAdapter):
    """Adapter for executing tasks via the Codex CLI in non-interactive mode."""

    def __init__(self, config_manager: Optional[CodexConfigManager] = None):
        self.config_manager = config_manager or CodexConfigManager()
        self.agent_manager = AgentCliManager()

    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        """
        Phase 1: Configuration Management
        """
        # 1. Load Skill Defaults from TOML
        skill_defaults: Dict[str, Any] = {}
        if skill.path:
            settings_path = skill.path / "assets" / "codex_config.toml"
            if settings_path.exists():
                try:
                    import tomlkit
                    with open(settings_path, "r") as f:
                        skill_defaults = tomlkit.parse(f.read())
                    logger.info(f"Loaded skill defaults from {settings_path}")
                except Exception as e:
                    logger.warning(f"Failed to load skill settings: {e}")
        
        # 2. Fuse Configuration
        try:
            profile_name_override = options.get("__codex_profile_name")
            profile_name = (
                profile_name_override.strip()
                if isinstance(profile_name_override, str)
                else ""
            )
            config_manager = self.config_manager
            if profile_name:
                if isinstance(self.config_manager, CodexConfigManager):
                    config_manager = CodexConfigManager(
                        config_path=self.config_manager.config_path,
                        profile_name=profile_name,
                    )
                else:
                    try:
                        setattr(config_manager, "profile_name", profile_name)
                    except Exception:
                        pass
            codex_overrides = self._extract_codex_overrides(options)
            fused_settings = config_manager.generate_profile_settings(skill_defaults, codex_overrides)
            active_profile_name = getattr(
                config_manager,
                "profile_name",
                CodexConfigManager.PROFILE_NAME,
            )
            logger.info("Updating Codex profile '%s' with fused settings", active_profile_name)
            
            # NOTE: Currently CodexConfigManager updates the GLOBAL user config.
            # Ideal architecture requires local config file passed to CLI via -c, 
            # but Codex CLI might not fully support isolation yet.
            # Stick to profile injection for now as documented in design.
            config_manager.update_profile(fused_settings)
            
            # Return path to global config as a placeholder since we modified it in-place
            return config_manager.config_path
            
        except ValueError as e:
            raise RuntimeError(f"Configuration Error: {e}")

    def _extract_codex_overrides(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Keep only Codex config fields; exclude runner runtime/interactivity controls."""
        overrides: Dict[str, Any] = {}

        raw_codex_config = options.get("codex_config")
        if isinstance(raw_codex_config, dict):
            for key, value in raw_codex_config.items():
                if not isinstance(key, str):
                    continue
                if key.startswith("__"):
                    continue
                if key in RUNNER_ONLY_OPTION_KEYS:
                    continue
                overrides[key] = value

        for key in CODEX_CONFIG_PASSTHROUGH_KEYS:
            if key not in options:
                continue
            value = options.get(key)
            if value is None:
                continue
            overrides[key] = value

        return overrides

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        """
        Phase 2: Environment Setup
        """
        # Copy skill to workspace to allow safe execution and patching
        # Just like Gemini, we give it a home in .codex/skills/
        codex_ws_dir = run_dir / ".codex"
        skills_target_dir = codex_ws_dir / "skills" / skill.id
        
        if skill.path:
            if skills_target_dir.exists():
                import shutil
                shutil.rmtree(skills_target_dir)
            try:
                import shutil
                shutil.copytree(skill.path, skills_target_dir)
                logger.info("Installed skill %s to %s", skill.id, skills_target_dir)
            except Exception:
                 logger.exception("Failed to install skill")
                 # Proceed with original path? No, standard requires workspace copy.
        
        # Always patch runtime contract/mode semantics; artifacts patch is optional.
        from ..services.skill_patcher import skill_patcher
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
        """
        Phase 3: Context & Prompt
        """
        # 1. Resolve Inputs (Strict Check) & Parameters
        from ..services.schema_validator import schema_validator
        input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir, input_data)
        if missing_required:
            raise ValueError(f"Missing required input files: {', '.join(missing_required)}")

        param_ctx = schema_validator.build_parameter_context(skill, input_data)

        # Fallback (Legacy)
        if not skill.schemas or "parameter" not in skill.schemas:
             param_ctx.update(input_data.get("input", {}))

        # 2. Template Resolution
        prompt_template_str = ""
        if skill.entrypoint and "prompts" in skill.entrypoint and "codex" in skill.entrypoint["prompts"]:
            prompt_template_str = skill.entrypoint["prompts"]["codex"]
        else:
            # Load default template
            template_path = Path(__file__).parent.parent / "assets" / "templates" / "codex_default.j2"
            if template_path.exists():
                prompt_template_str = template_path.read_text(encoding='utf-8')
            else:
                prompt_template_str = 'Execute skill "{{ skill.id }}" with inputs: {{ params_json }}'

        # 3. Render
        from jinja2 import Template
        template = Template(prompt_template_str)
        
        # Construct specific "Codex-friendly" JSON context
        combined_data = {"input": input_ctx, "parameter": param_ctx}
        params_json = json.dumps(combined_data, indent=2)
        
        prompt = template.render(
            skill=skill,
            skill_id=skill.id,
            params_json=params_json,
            input=input_ctx,
            parameter=param_ctx,
            run_dir=str(run_dir)
        )
            
        # Log Prompt
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        with open(logs_dir / "prompt.txt", "w") as f:
            f.write(prompt)
            
        return prompt

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        """
        Phase 4: Execution (With optional streaming)
        """
        resume_handle = options.get("__resume_session_handle")
        if isinstance(resume_handle, dict):
            cmd = self.build_resume_command(
                prompt=prompt,
                options=options,
                session_handle=EngineSessionHandle.model_validate(resume_handle),
            )
        else:
            cmd = self.build_start_command(prompt=prompt, options=options)
        
        logger.info("Executing Codex command: %s", " ".join(cmd))
        
        # Execute
        env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
        
        proc = await self._create_subprocess(
            *cmd,
            cwd=run_dir,
            env=env,
        )
        return await self._capture_process_output(proc, run_dir, options, "Codex")

    def _resolve_codex_command(self) -> Path:
        cmd = self.agent_manager.resolve_engine_command("codex")
        if cmd is None:
            raise RuntimeError("Codex CLI not found in managed prefix")
        return cmd

    def _apply_landlock_flag_fallback(self, flags: list[str]) -> list[str]:
        if os.environ.get("LANDLOCK_ENABLED") != "0":
            return flags
        replaced = ["--yolo" if token == "--full-auto" else token for token in flags]
        if "--yolo" in replaced:
            return replaced
        return replaced

    def _strip_resume_profile_flags(self, flags: list[str]) -> list[str]:
        filtered: list[str] = []
        skip_next = False
        for token in flags:
            if skip_next:
                skip_next = False
                continue
            if token == "-p":
                skip_next = True
                continue
            if token == "--profile":
                skip_next = True
                continue
            if token.startswith("--profile="):
                continue
            filtered.append(token)
        return filtered

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="codex", action=action)

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        executable = str(self._resolve_codex_command())
        if passthrough_args is not None:
            fallback_flags = self._apply_landlock_flag_fallback(list(passthrough_args))
            return [executable, *fallback_flags]
        default_flags = self._resolve_profile_flags(action="start", use_profile_defaults=use_profile_defaults)
        merged_flags = merge_cli_args(default_flags, [])
        merged_flags = self._apply_landlock_flag_fallback(merged_flags)
        return [executable, "exec", *merged_flags, prompt]

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        """
        Phase 5: Result Parsing (NDJSON Stream Support)
        """
        last_message_text = ""
        
        # 1. Parse Stream
        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # Looking for: {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
                if event.get("type") == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        last_message_text = item.get("text", "")
            except json.JSONDecodeError:
                continue
        
        if not last_message_text:
            # Fallback: Maybe the whole output is just JSON (if not streaming mode?)
            # or maybe it's just raw text.
            last_message_text = raw_stdout

        # 2. Extract JSON from Message Text
        result, repair_level = self._parse_json_with_deterministic_repair(last_message_text)
        if result is not None:
            return self._build_turn_result_from_payload(result, repair_level)
        logger.warning(f"Failed to parse Codex result. Last message: {last_message_text[:100]}...")
        return self._turn_error(message="failed to parse codex output")

    def extract_session_handle(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        first_event: Optional[dict[str, Any]] = None
        for line in raw_stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                first_event = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise RuntimeError("SESSION_RESUME_FAILED: invalid codex json stream") from exc
            break
        if not first_event:
            raise RuntimeError("SESSION_RESUME_FAILED: codex output is empty")
        if first_event.get("type") != "thread.started":
            raise RuntimeError("SESSION_RESUME_FAILED: missing thread.started event")
        thread_id = first_event.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise RuntimeError("SESSION_RESUME_FAILED: missing thread_id")
        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=thread_id.strip(),
            created_at_turn=turn_index,
        )

    def build_resume_command(
        self,
        prompt: str,
        options: Dict[str, Any],
        session_handle: EngineSessionHandle,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        thread_id = session_handle.handle_value.strip()
        if not thread_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty codex thread id")
        executable = str(self._resolve_codex_command())
        if passthrough_args is not None:
            flags = [
                token
                for token in passthrough_args
                if isinstance(token, str) and token.startswith("-")
            ]
            defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=False)
            merged = merge_cli_args(defaults, flags)
            merged = self._strip_resume_profile_flags(merged)
            merged = self._apply_landlock_flag_fallback(merged)
            return [executable, "exec", "resume", *merged, thread_id, prompt]
        defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=use_profile_defaults)
        merged = merge_cli_args(defaults, [])
        merged = self._strip_resume_profile_flags(merged)
        merged = self._apply_landlock_flag_fallback(merged)
        return [executable, "exec", "resume", *merged, thread_id, prompt]

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

        for row in records:
            payload = row["payload"]
            row_session_id = find_session_id(payload)
            if row_session_id and not session_id:
                session_id = row_session_id
            payload_type = payload.get("type")
            if isinstance(payload_type, str):
                structured_types.append(payload_type)
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
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

        stdout_turn_completed = any(
            isinstance(row["payload"], dict) and row["payload"].get("type") == "turn.completed"
            for row in records
        )
        pty_turn_completed = any(
            isinstance(row["payload"], dict) and row["payload"].get("type") == "turn.completed"
            for row in pty_records
        )
        use_pty_fallback = (not assistant_messages and pty_records) or (
            not stdout_turn_completed and pty_turn_completed
        )

        if use_pty_fallback:
            diagnostics.append("PTY_FALLBACK_USED")
            for row in pty_records:
                payload = row["payload"]
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if payload.get("type") != "item.completed":
                    continue
                item = payload.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
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

        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        return {
            "parser": "codex_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": list(raw_rows),
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
