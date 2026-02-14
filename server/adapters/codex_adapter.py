import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from server.services.codex_config_manager import CodexConfigManager
from server.services.agent_cli_manager import AgentCliManager

logger = logging.getLogger(__name__)

from .base import EngineAdapter, ProcessExecutionResult
from ..models import SkillManifest

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
            fused_settings = self.config_manager.generate_profile_settings(skill_defaults, options)
            logger.info(f"Updating Codex profile '{CodexConfigManager.PROFILE_NAME}' with fused settings")
            
            # NOTE: Currently CodexConfigManager updates the GLOBAL user config.
            # Ideal architecture requires local config file passed to CLI via -c, 
            # but Codex CLI might not fully support isolation yet.
            # Stick to profile injection for now as documented in design.
            self.config_manager.update_profile(fused_settings)
            
            # Return path to global config as a placeholder since we modified it in-place
            return self.config_manager.config_path
            
        except ValueError as e:
            raise RuntimeError(f"Configuration Error: {e}")

    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path) -> Path:
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
            except Exception as e:
                 logger.exception("Failed to install skill")
                 # Proceed with original path? No, standard requires workspace copy.
        
        # Patching
        if skill.artifacts:
            from ..services.skill_patcher import skill_patcher
            skill_patcher.patch_skill_md(skills_target_dir, skill.artifacts)
                
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
        # Construct Command
        sandbox_flag = "--full-auto"
        if os.environ.get("LANDLOCK_ENABLED") == "0":
            sandbox_flag = "--yolo"
        cmd = [
            str(self._resolve_codex_command()),
            "exec",
            sandbox_flag,
            "--skip-git-repo-check",
            "--json",
            "-p", CodexConfigManager.PROFILE_NAME,
            prompt
        ]
        
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

    def _parse_output(self, raw_stdout: str) -> Tuple[Optional[Dict[str, Any]], str]:
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
        # Same regex logic as Gemini
        result, repair_level = self._parse_json_with_deterministic_repair(last_message_text)
        if result is not None:
            return result, repair_level
        logger.warning(f"Failed to parse Codex result. Last message: {last_message_text[:100]}...")
        return None, "none"
