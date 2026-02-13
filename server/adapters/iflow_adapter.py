import os
import json
import logging
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from .base import EngineAdapter, ProcessExecutionResult
from ..models import SkillManifest
from ..services.config_generator import config_generator
from ..services.skill_patcher import skill_patcher
from ..services.schema_validator import schema_validator
from ..services.agent_cli_manager import AgentCliManager
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

    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path) -> Path:
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
             except Exception as e:
                 logger.exception("Failed to copy skill")
                 
        # Patching
        if skill.artifacts:
            skill_patcher.patch_skill_md(skills_target_dir, skill.artifacts)
            
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
        
        # Log prompt
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
        Phase 4: Execution
        """
        env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
        cmd_parts = []

        # UV Wrapping
        if skill.runtime and skill.runtime.dependencies:
            cmd_parts.extend(["uv", "run"])
            for dep in skill.runtime.dependencies:
                cmd_parts.append(f"--with={dep}")

        # Base Command
        iflow_cmd = self.agent_manager.resolve_engine_command("iflow")
        if iflow_cmd is None:
            raise RuntimeError("iFlow CLI not found in managed prefix")
        cmd_parts.extend([
            str(iflow_cmd),
            "--yolo",
            "-p", prompt
        ])
        
        logger.info("Executing iFlow command: %s in %s", " ".join(cmd_parts), run_dir)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(run_dir),
            env=env
        )
        return await self._capture_process_output(proc, run_dir, options, "iFlow")

    def _parse_output(self, raw_stdout: str) -> Optional[Dict[str, Any]]:
        """
        Phase 5: Result Parsing
        Extracts JSON from the output.
        """
        import re
        
        # 1. Regex search for JSON block
        result = self._extract_json_from_text(raw_stdout)
        if result is not None:
            return result
            
        logger.warning("Failed to parse JSON result from iFlow output")
        return None
