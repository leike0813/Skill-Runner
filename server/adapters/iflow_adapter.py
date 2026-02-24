import os
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from .base import (
    EngineAdapter,
    ProcessExecutionResult,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
    RuntimeStreamRawRow,
)
from ..models import AdapterTurnResult, EngineSessionHandle, EngineSessionHandleType, SkillManifest
from ..services.config_generator import config_generator
from ..services.skill_patcher import skill_patcher
from ..services.schema_validator import schema_validator
from ..services.agent_cli_manager import AgentCliManager
from ..services.engine_command_profile import engine_command_profile, merge_cli_args
from ..services.runtime_parse_utils import (
    dedup_assistant_messages,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
from jinja2 import Template

logger = logging.getLogger(__name__)

class IFlowAdapter(EngineAdapter):
    """
    Adapter for executing tasks via the iFlow CLI in non-interactive mode.
    
    Execution Strategy:
    1. Generates a project-specific configuration in `.iflow/settings.json`.
    2. Executes `iflow` in the run directory.
    3. Uses `--yolo` and `-p` flags for headless operation.
    """
    def __init__(self) -> None:
        self.agent_manager = AgentCliManager()
    
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        """
        Phase 1: Configuration Management
        Generates .iflow/settings.json in the run workspace.
        """
        # 1. Base Defaults (Adapter Hardcoded)
        
        # 2. Skill Defaults (assets/iflow_settings.json in skill repo)
        skill_defaults = {}
        if skill.path:
            skill_settings_path = skill.path / "assets" / "iflow_settings.json"
            if skill_settings_path.exists():
                try:
                    with open(skill_settings_path, "r") as f:
                        skill_defaults = json.load(f)
                    logger.info("Loaded skill defaults from %s", skill_settings_path)
                except Exception as e:
                    logger.exception("Failed to load skill defaults")
        
        # 3. User Overrides (runtime options)
        user_overrides: Dict[str, Any] = {}
        
        # Mappings from runtime options to iFlow settings
        if "model" in options:
            user_overrides["modelName"] = options["model"]
            
        # Others can be mapped here as needed (api_key, base_url, etc)
        # sandbox is a special case, often controlled by system but can be overridden if allowed?
        # gemini adapter doesn't map sandbox from options explicitly, mostly enforced.
        
        # 4. System Enforced (server/assets/configs/iflow_enforced.json)
        enforced_config = {}
        enforced_path = Path(__file__).parent.parent / "assets" / "configs" / "iflow_enforced.json"
        if enforced_path.exists():
             with open(enforced_path, "r") as f:
                enforced_config = json.load(f)

        layers = [skill_defaults, user_overrides]
        # Support explicit iflow config passed in options (similar to gemini_config)
        if "iflow_config" in options:
            layers.append(options["iflow_config"])
            
        layers.append(enforced_config)
        
        target_path = run_dir / ".iflow" / "settings.json"
        
        try:
            config_generator.generate_config(
                schema_name="iflow_settings_schema.json",
                config_layers=layers,
                output_path=target_path
            )
            return target_path
        except Exception as e:
            raise RuntimeError(f"Failed to generate iFlow configuration: {e}")

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        """
        Phase 2: Environment Setup
        Copies skill to .iflow/skills/{id} and patches SKILL.md.
        """
        # iFlow might not have a strict "skills" directory requirement like Codex/Gemini?
        # But following the pattern ensures isolation.
        iflow_ws_dir = run_dir / ".iflow"
        skills_target_dir = iflow_ws_dir / "skills" / skill.id
        
        if skill.path:
             if skills_target_dir.exists():
                 shutil.rmtree(skills_target_dir)
             try:
                 shutil.copytree(skill.path, skills_target_dir)
                 logger.info("Installed skill %s to %s", skill.id, skills_target_dir)
             except Exception:
                 logger.exception("Failed to copy skill")
                 
        # Always patch runtime contract/mode semantics; artifacts patch is optional.
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
        # 1. Resolve Inputs & Parameters
        # (Similar logic to Codex/Gemini - extracting files and params)
        input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir, input_data)
        if missing_required:
            raise ValueError(f"Missing required input files: {', '.join(missing_required)}")
                    
        param_ctx = schema_validator.build_parameter_context(skill, input_data)
                    
        # 2. Template Resolution
        prompt_template_str = ""
        # Check for inline prompt template in manifest
        if skill.entrypoint and "prompts" in skill.entrypoint and "iflow" in skill.entrypoint["prompts"]:
            prompt_template_str = skill.entrypoint["prompts"]["iflow"]
        else:
            # Load default template
            template_path = Path(__file__).parent.parent / "assets" / "templates" / "iflow_default.j2"
            if template_path.exists():
                prompt_template_str = template_path.read_text(encoding='utf-8')
            else:
                 prompt_template_str = '{{ input_prompt }}' # Minimal fallback

        # 3. Render
        template = Template(prompt_template_str)
        
        # We need a primary instruction/input_prompt for the template
        # Usually checking 'instruction' or 'prompt' param
        main_prompt = param_ctx.get("prompt", f"Execute skill {skill.id}")

        prompt = template.render(
            skill=skill,
            input_prompt=main_prompt,
            input=input_ctx,
            parameter=param_ctx,
            run_dir=str(run_dir)
        )
        
        return prompt

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        """
        Phase 4: Execution
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
        
        logger.info("Executing iFlow command: %s in %s", " ".join(cmd_parts), run_dir)
        
        proc = await self._create_subprocess(
            *cmd_parts,
            cwd=run_dir,
            env=env,
        )
        return await self._capture_process_output(proc, run_dir, options, "iFlow")

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="iflow", action=action)

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        iflow_cmd = self.agent_manager.resolve_engine_command("iflow")
        if iflow_cmd is None:
            raise RuntimeError("iFlow CLI not found in managed prefix")
        if passthrough_args is not None:
            return [str(iflow_cmd), *passthrough_args]
        defaults = self._resolve_profile_flags(action="start", use_profile_defaults=use_profile_defaults)
        merged = merge_cli_args(defaults, [])
        return [str(iflow_cmd), *merged, "-p", prompt]

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        """
        Phase 5: Result Parsing
        Extracts JSON from the output.
        """
        result, repair_level = self._parse_json_with_deterministic_repair(raw_stdout)
        if result is not None:
            return self._build_turn_result_from_payload(result, repair_level)
            
        logger.warning("Failed to parse JSON result from iFlow output")
        return self._turn_error(message="failed to parse iflow output")

    def extract_session_handle(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        match = re.search(r'"session-id"\s*:\s*"([^"]+)"', raw_stdout)
        if not match:
            raise RuntimeError("SESSION_RESUME_FAILED: missing iflow session-id")
        session_id = match.group(1).strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty iflow session-id")
        return EngineSessionHandle(
            engine="iflow",
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
            raise RuntimeError("SESSION_RESUME_FAILED: empty iflow session-id")
        iflow_cmd = self.agent_manager.resolve_engine_command("iflow")
        if iflow_cmd is None:
            raise RuntimeError("iFlow CLI not found in managed prefix")
        if passthrough_args is not None:
            flags = [
                token
                for token in passthrough_args
                if isinstance(token, str) and token.startswith("-")
            ]
            merged = merge_cli_args([], flags)
            return [str(iflow_cmd), "--resume", session_id, *merged, "-p", prompt]
        defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=use_profile_defaults)
        merged = merge_cli_args(defaults, [])
        return [
            str(iflow_cmd),
            "--resume",
            session_id,
            *merged,
            "-p",
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
        stderr_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stderr", stderr_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        diagnostics: list[str] = []
        split_merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows] if row["line"]])
        pty_merged = "\n".join([row["line"] for row in pty_rows if row["line"]])
        merged = "\n".join(
            [row["line"] for row in [*stdout_rows, *stderr_rows, *pty_rows] if row["line"]]
        )
        cleaned_split = re.sub(r"<Execution Info>[\s\S]*?</Execution Info>", "", split_merged).strip()
        cleaned_pty = re.sub(r"<Execution Info>[\s\S]*?</Execution Info>", "", pty_merged).strip()
        use_pty_fallback = (not cleaned_split) and bool(cleaned_pty)
        cleaned = cleaned_pty if use_pty_fallback else cleaned_split
        assistant_messages: list[RuntimeAssistantMessage] = []
        raw_rows: list[RuntimeStreamRawRow] = []
        confidence = 0.45

        if cleaned:
            assistant_messages.append({"text": cleaned, "raw_ref": None})
            confidence = 0.65
            if use_pty_fallback:
                diagnostics.append("PTY_FALLBACK_USED")
        else:
            raw_rows.extend(stdout_rows)
            raw_rows.extend(stderr_rows)
            raw_rows.extend(pty_rows)
            diagnostics.append("LOW_CONFIDENCE_PARSE")

        if stdout_rows and stderr_rows:
            diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")

        return {
            "parser": "iflow_text",
            "confidence": confidence,
            "session_id": find_session_id_in_text(merged),
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": ["iflow.execution_info"],
        }
