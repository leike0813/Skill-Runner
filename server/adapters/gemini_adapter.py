import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from ..models import AdapterTurnResult, EngineSessionHandle, EngineSessionHandleType, SkillManifest
from .base import EngineAdapter, ProcessExecutionResult
from ..config import config
from ..services.config_generator import config_generator
from ..services.skill_patcher import skill_patcher
from ..services.schema_validator import schema_validator
from ..services.agent_cli_manager import AgentCliManager
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
            except Exception as e:
                 logger.exception("Failed to install skill")
                 # We might want to re-raise here if critical? 
                 # For now, print error, but execution might fail later.

            # Patching
            if skill.artifacts:
                skill_patcher.patch_skill_md(
                    skills_target_dir,
                    skill.artifacts,
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
                
        gemini_cmd = self.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        resume_handle = options.get("__resume_session_handle")
        if isinstance(resume_handle, dict):
            cmd_parts.extend(
                self.build_resume_command(
                    prompt=prompt,
                    options=options,
                    session_handle=EngineSessionHandle.model_validate(resume_handle),
                )
            )
        else:
            cmd_parts.extend([str(gemini_cmd)])
            if self._resolve_execution_mode(options) == "auto":
                cmd_parts.append("--yolo")
            cmd_parts.append(prompt)
        
        logger.info("Executing Gemini CLI: %s in %s", " ".join(cmd_parts), run_dir)
        
        proc = await self._create_subprocess(
            *cmd_parts,
            cwd=run_dir,
            env=env,
        )
        return await self._capture_process_output(proc, run_dir, options, "Gemini")

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
    ) -> list[str]:
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty gemini session_id")
        gemini_cmd = self.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        return [
            str(gemini_cmd),
            "--resume",
            session_id,
            prompt,
        ]

    def _extract_session_id(self, raw_stdout: str) -> Optional[str]:
        try:
            payload = json.loads(raw_stdout)
        except json.JSONDecodeError:
            return None
        return self._find_session_id(payload)

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
