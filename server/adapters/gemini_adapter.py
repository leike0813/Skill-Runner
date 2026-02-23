import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from ..models import AdapterTurnResult, EngineSessionHandle, EngineSessionHandleType, SkillManifest
from .base import (
    EngineAdapter,
    ProcessExecutionResult,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
    RuntimeStreamRawRow,
)
from ..config import config
from ..services.config_generator import config_generator
from ..services.skill_patcher import skill_patcher
from ..services.schema_validator import schema_validator
from ..services.agent_cli_manager import AgentCliManager
from ..services.engine_command_profile import engine_command_profile, merge_cli_args
from ..services.runtime_parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    extract_json_document_with_span,
    extract_fenced_or_plain_json,
    find_session_id,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
from jinja2 import Template
import shutil

class GeminiAdapter(EngineAdapter):
    def __init__(self) -> None:
        self.agent_manager = AgentCliManager()
    
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        """
        Phase 1: Configuration Management
        """
        gemini_config_dir = run_dir / ".gemini"
        settings_path = gemini_config_dir / "settings.json"
        
        # Layer 1: Base (Minimal)
        
        # Layer 2: Skill Defaults
        skill_defaults = {}
        if skill.path:
            skill_assets = skill.path / "assets"
            gemini_settings_file = skill_assets / "gemini_settings.json"
            if gemini_settings_file.exists():
                try:
                    with open(gemini_settings_file, "r") as f:
                        skill_defaults = json.load(f)
                    logger.info("Loaded skill defaults from %s", gemini_settings_file)
                except Exception as e:
                    logger.exception("Failed to load skill defaults")
        
        # Layer 3: User Overrides
        user_overrides: Dict[str, Any] = {}
        if "model" in options:
             user_overrides.setdefault("model", {})["name"] = options["model"]
        if "temperature" in options:
             user_overrides.setdefault("model", {})["temperature"] = float(options["temperature"])
        if "max_tokens" in options:
             user_overrides.setdefault("model", {})["maxOutputTokens"] = int(options["max_tokens"])
        
        # Layer 4: System Enforced
        enforced_config_path = Path(__file__).parent.parent / "assets" / "configs" / "gemini_enforced.json"
        project_enforced = {}
        if enforced_config_path.exists():
             try:
                with open(enforced_config_path, "r") as f:
                    project_enforced = json.load(f)
             except Exception as e:
                 logger.exception("Failed to load project enforced config")
        
        layers = [skill_defaults, user_overrides]
        if "gemini_config" in options:
            layers.append(options["gemini_config"])
        layers.append(project_enforced)

        # Ensure directory exists (usually done by WorkspaceManager, but config_generator needs parent)
        # run_dir exists, .gemini might not
        # config_generator handles mkdir? No, it takes path.
        # Ensure parent
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        config_generator.generate_config("gemini_settings_schema.json", layers, settings_path)
        return settings_path

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        """
        Phase 2: Environment Setup (Install & Patch)
        """
        gemini_config_dir = config_path.parent
        
        if skill.path:
            skills_target_dir = gemini_config_dir / "skills" / skill.id
            if skills_target_dir.exists():
                shutil.rmtree(skills_target_dir)
            
            try:
                shutil.copytree(skill.path, skills_target_dir)
                logger.info("Installed skill %s to %s", skill.id, skills_target_dir)
            except Exception:
                 logger.exception("Failed to install skill")
                 # We might want to re-raise here if critical? 
                 # For now, print error, but execution might fail later.

            # Always patch runtime contract/mode semantics; artifacts patch is optional.
            skill_patcher.patch_skill_md(
                skills_target_dir,
                skill.artifacts or [],
                execution_mode=self._resolve_execution_mode(options),
            )
                
            return skills_target_dir
        return Path(gemini_config_dir / "skills" / "unknown") # Should verify earlier

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: Dict[str, Any]) -> str:
        """
        Phase 3: Context & Prompt
        """
        params_json = json.dumps(input_data, indent=2)
        input_file_path = run_dir / "input.json" 
        
        # 1. Template Resolution
        prompt_template_str = ""
        if skill.entrypoint and "prompts" in skill.entrypoint and "gemini" in skill.entrypoint["prompts"]:
             prompt_template_str = skill.entrypoint["prompts"]["gemini"]
        else:
             template_path = Path(config.GEMINI.DEFAULT_PROMPT_TEMPLATE)
             if template_path.exists():
                 prompt_template_str = template_path.read_text(encoding='utf-8')
             else:
                 prompt_template_str = "Please call the skill named \"{{ skill.id }}\"."

        # 2. Context Resolution (Inputs & Parameters)
        input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir, input_data)
        if missing_required:
            raise ValueError(f"Missing required input files: {', '.join(missing_required)}")

        param_ctx = schema_validator.build_parameter_context(skill, input_data)
        
        # Fallback Logic (Legacy)
        if not skill.schemas or "parameter" not in skill.schemas:
             param_ctx.update(input_data.get("input", {}))
        
        # 3. Render
        gemini_config_dir = run_dir / ".gemini"
        template = Template(prompt_template_str)
        prompt = template.render(
            skill=skill,
            skill_id=skill.id,
            input_file=input_file_path.name,
            params_json=params_json,
            input=input_ctx,
            parameter=param_ctx,
            run_dir=str(run_dir),
            skill_dir=str(gemini_config_dir / "skills" / skill.id)
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
        env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
        cmd_parts = []
        
        # UV Wrapping
        if skill.runtime and skill.runtime.dependencies:
            cmd_parts.extend(["uv", "run"])
            for dep in skill.runtime.dependencies:
                cmd_parts.append(f"--with={dep}")
                
        resume_handle = options.get("__resume_session_handle")
        if isinstance(resume_handle, dict):
            engine_command = self.build_resume_command(
                prompt=prompt,
                options=options,
                session_handle=EngineSessionHandle.model_validate(resume_handle),
            )
        else:
            engine_command = self.build_start_command(prompt=prompt, options=options)
        cmd_parts.extend(engine_command)
        
        logger.info("Executing Gemini CLI: %s in %s", " ".join(cmd_parts), run_dir)
        
        proc = await self._create_subprocess(
            *cmd_parts,
            cwd=run_dir,
            env=env,
        )
        return await self._capture_process_output(proc, run_dir, options, "Gemini")

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="gemini", action=action)

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        gemini_cmd = self.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        if passthrough_args is not None:
            return [str(gemini_cmd), *passthrough_args]
        defaults = self._resolve_profile_flags(action="start", use_profile_defaults=use_profile_defaults)
        flags = merge_cli_args(defaults, [])
        return [str(gemini_cmd), *flags, prompt]

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        """
        Phase 5: Result Parsing
        """
        response_text = raw_stdout
        used_envelope_response = False
        try:
            envelope = json.loads(raw_stdout)
            if isinstance(envelope, dict) and "response" in envelope:
                used_envelope_response = True
                response = envelope["response"]
                if isinstance(response, str):
                    response_text = response
                else:
                    response_text = json.dumps(response, ensure_ascii=False)
            elif isinstance(envelope, dict) and "response" not in envelope and "error" in envelope:
                 logger.error("Gemini CLI Error: %s", envelope["error"])
                 return self._turn_error(message="gemini cli error envelope")
        except json.JSONDecodeError:
            pass

        result, repair_level = self._parse_json_with_deterministic_repair(response_text)
        if result is None:
            return self._turn_error(message="failed to parse gemini output")
        if used_envelope_response and repair_level == "none":
            repair_level = "deterministic_generic"
        return self._build_turn_result_from_payload(result, repair_level)

    def extract_session_handle(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        session_id = self._extract_session_id(raw_stdout)
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: missing gemini session_id")
        return EngineSessionHandle(
            engine="gemini",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=session_id,
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
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty gemini session_id")
        gemini_cmd = self.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        if passthrough_args is not None:
            flags = [
                token
                for token in passthrough_args
                if isinstance(token, str) and token.startswith("-")
            ]
            merged = merge_cli_args([], flags)
            return [str(gemini_cmd), "--resume", session_id, *merged, prompt]
        defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=use_profile_defaults)
        merged = merge_cli_args(defaults, [])
        return [
            str(gemini_cmd),
            "--resume",
            session_id,
            *merged,
            prompt,
        ]

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        stderr_rows = stream_lines_with_offsets("stderr", stderr_raw)
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")

        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        confidence = 0.5
        consumed_ranges: dict[str, list[tuple[int, int]]] = {
            "stdout": [],
            "stderr": [],
            "pty": [],
        }

        def _mark_consumed(stream: str, byte_from: int, byte_to: int) -> None:
            if byte_from < 0 or byte_to <= byte_from:
                return
            bucket = consumed_ranges.get(stream)
            if bucket is None:
                return
            bucket.append((byte_from, byte_to))

        def _consume_payload(
            *,
            payload: Any,
            stream: str,
            byte_from: int,
            byte_to: int,
            structured_type: str,
        ) -> bool:
            nonlocal session_id, confidence
            if not isinstance(payload, dict):
                return False
            if structured_type:
                structured_types.append(structured_type)
            consumed = False
            row_session_id = find_session_id(payload)
            if row_session_id and not session_id:
                session_id = row_session_id
            response = payload.get("response")
            if isinstance(response, str) and response.strip():
                assistant_messages.append(
                    {
                        "text": response,
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": byte_from,
                            "byte_to": byte_to,
                        },
                    }
                )
                confidence = max(confidence, 0.9 if stream == "stderr" else 0.8)
                consumed = True
            elif response is not None:
                assistant_messages.append(
                    {
                        "text": json.dumps(response, ensure_ascii=False),
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": byte_from,
                            "byte_to": byte_to,
                        },
                    }
                )
                confidence = max(confidence, 0.8 if stream == "stderr" else 0.75)
                consumed = True
            if row_session_id:
                consumed = True
            if consumed:
                _mark_consumed(stream, byte_from, byte_to)
            return consumed

        def _consume_stream_records(records: list[dict[str, Any]]) -> bool:
            consumed_any = False
            for row in records:
                if _consume_payload(
                    payload=row["payload"],
                    stream=str(row["stream"]),
                    byte_from=int(row["byte_from"]),
                    byte_to=int(row["byte_to"]),
                    structured_type="gemini.stream_response",
                ):
                    consumed_any = True
            return consumed_any

        def _document_json_fallback(*, stream: str, text: str, raw_size: int) -> bool:
            doc = extract_json_document_with_span(text)
            if doc is None:
                return False
            payload, byte_from, byte_to = doc
            return _consume_payload(
                payload=payload,
                stream=stream,
                byte_from=byte_from,
                byte_to=byte_to if byte_to > byte_from else raw_size,
                structured_type="gemini.stream_response" if stream != "stderr" else "gemini.response",
            )

        used_stream_json_fallback = False
        if stderr_text.strip():
            stderr_used = _document_json_fallback(stream="stderr", text=stderr_text, raw_size=len(stderr_raw))
            if not stderr_used:
                fallback = extract_fenced_or_plain_json(stderr_text)
                if fallback is not None:
                    stderr_used = _consume_payload(
                        payload=fallback,
                        stream="stderr",
                        byte_from=0,
                        byte_to=len(stderr_raw),
                        structured_type="gemini.fenced_json_fallback",
                    )
                if not stderr_used:
                    diagnostics.append("GEMINI_STDERR_JSON_PARSE_FAILED")

        if not assistant_messages and stdout_text.strip():
            stdout_used = _document_json_fallback(stream="stdout", text=stdout_text, raw_size=len(stdout_raw))
            if not stdout_used:
                stdout_records, _ = collect_json_parse_errors(stdout_rows)
                stdout_used = _consume_stream_records(stdout_records)
            if stdout_used:
                used_stream_json_fallback = True

        pty_used = False
        if not assistant_messages and pty_text.strip():
            pty_used = _document_json_fallback(stream="pty", text=pty_text, raw_size=len(pty_raw))
            if not pty_used:
                pty_records, _ = collect_json_parse_errors(pty_rows)
                pty_used = _consume_stream_records(pty_records)
            if pty_used:
                diagnostics.append("PTY_FALLBACK_USED")
                used_stream_json_fallback = True

        if used_stream_json_fallback:
            diagnostics.append("GEMINI_STREAM_JSON_FALLBACK_USED")

        if not session_id:
            session_id = (
                find_session_id_in_text(stderr_text)
                or find_session_id_in_text(stdout_text)
                or find_session_id_in_text(pty_text)
            )

        def _row_overlaps_consumed(row: RuntimeStreamRawRow) -> bool:
            ranges = consumed_ranges.get(row["stream"], [])
            if not ranges:
                return False
            row_start = int(row["byte_from"])
            row_end = int(row["byte_to"])
            for start, end in ranges:
                if row_start < end and row_end > start:
                    return True
            return False

        raw_candidates: list[RuntimeStreamRawRow] = [*stdout_rows, *stderr_rows]
        if pty_used:
            raw_candidates.extend(pty_rows)
        raw_rows = [row for row in raw_candidates if not _row_overlaps_consumed(row)]

        if any(row["stream"] == "stdout" for row in raw_rows):
            diagnostics.append("GEMINI_STDOUT_NOISE")

        return {
            "parser": "gemini_json",
            "confidence": confidence,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": list(dict.fromkeys(structured_types)),
        }

    def _extract_session_id(self, raw_stdout: str) -> Optional[str]:
        try:
            payload = json.loads(raw_stdout)
        except json.JSONDecodeError:
            return find_session_id_in_text(raw_stdout)
        return self._find_session_id(payload) or find_session_id_in_text(raw_stdout)

    def _find_session_id(self, payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            value = payload.get("session_id")
            if isinstance(value, str) and value.strip():
                return value.strip()
            for child in payload.values():
                found = self._find_session_id(child)
                if found:
                    return found
            return None
        if isinstance(payload, list):
            for item in payload:
                found = self._find_session_id(item)
                if found:
                    return found
        return None


logger = logging.getLogger(__name__)
