import asyncio
import os
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from ..models import SkillManifest
from .base import EngineAdapter, EngineRunResult
from ..config import config
from ..services.config_generator import config_generator
from ..services.skill_patcher import skill_patcher
from ..services.schema_validator import schema_validator
from jinja2 import Template
import shutil

class GeminiAdapter(EngineAdapter):
    
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

    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path) -> Path:
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
                skill_patcher.patch_skill_md(skills_target_dir, skill.artifacts)
                
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
        input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir)
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

    async def _execute_process(self, prompt: str, run_dir: Path, skill: SkillManifest, options: Dict[str, Any]) -> tuple[int, str, str]:
        """
        Phase 4: Execution (With optional streaming)
        """
        env = os.environ.copy()
        cmd_parts = []
        
        # UV Wrapping
        if skill.runtime and skill.runtime.dependencies:
            cmd_parts.extend(["uv", "run"])
            for dep in skill.runtime.dependencies:
                cmd_parts.append(f"--with={dep}")
                
        # Base Command
        cmd_parts.extend([
            "gemini",
            "--yolo",
            prompt
        ])
        
        logger.info("Executing Gemini CLI: %s in %s", " ".join(cmd_parts), run_dir)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(run_dir),
            env=env
        )
        return await self._capture_process_output(proc, run_dir, options, "Gemini")

    def _parse_output(self, raw_stdout: str) -> Optional[Dict[str, Any]]:
        """
        Phase 5: Result Parsing
        """
        response_text = raw_stdout
        try:
            envelope = json.loads(raw_stdout)
            if isinstance(envelope, dict) and "response" in envelope:
                response_text = envelope["response"]
            elif isinstance(envelope, dict) and "response" not in envelope and "error" in envelope:
                 logger.error("Gemini CLI Error: %s", envelope["error"])
                 return None
        except json.JSONDecodeError:
            pass
            
        return self._extract_json_from_text(response_text)


logger = logging.getLogger(__name__)
