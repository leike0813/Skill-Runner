from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Iterable
import asyncio
import json
import re
import logging
from pathlib import Path
from ..models import SkillManifest

class EngineRunResult:
    """
    Standardized payload returned by an EngineAdapter execution.
    Contains raw outputs, file paths, and artifact metadata.
    """
    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        output_file_path: Optional[Path] = None,
        artifacts_created: List[Path] = []
    ):
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.output_file_path = output_file_path
        self.artifacts_created = artifacts_created

logger = logging.getLogger(__name__)


class EngineAdapter(ABC):
    """
    Abstract Base Class for Execution Adapters (e.g. Gemini, Codex).
    
    Defines the standard 5-phase execution lifecycle:
    1. Configuration
    2. Environment Setup
    3. Context & Prompt
    4. Execution
    5. Result Parsing
    """
    
    async def run(
        self,
        skill: SkillManifest,
        input_data: Dict[str, Any],
        run_dir: Path,
        options: Dict[str, Any]
    ) -> EngineRunResult:
        """
        Orchestrates the standard execution lifecycle.
        Subclasses should implement the phases, not override this method unless absolutely necessary.
        """
        # 1. Configuration
        config_path = self._construct_config(skill, run_dir, options)
        
        # 2. Environment Setup
        installed_skill_dir = self._setup_environment(skill, run_dir, config_path)
        
        # 3. Context & Prompt
        prompt = self._build_prompt(skill, run_dir, input_data)
        
        # 4. Execution
        # We assume command construction + execution happens here
        exit_code, stdout, stderr = await self._execute_process(prompt, run_dir, skill, options)
        
        # 5. Result Parsing
        result_payload = self._parse_output(stdout)
        
        # 5.1 Artifact Scanning (Standardized here or in subclass? Standard here is better)
        artifacts_dir = run_dir / "artifacts"
        artifacts = list(artifacts_dir.glob("**/*")) if artifacts_dir.exists() else []
        
        # 5.2 Write Result Json if parsed
        result_path = run_dir / "result" / "result.json"
        if result_payload:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                import json
                json.dump(result_payload, f, indent=2)
                
        return EngineRunResult(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            output_file_path=result_path if result_path.exists() else None,
            artifacts_created=artifacts
        )

    async def _capture_process_output(self, proc, run_dir: Path, options: Dict[str, Any], prefix: str) -> tuple[int, str, str]:
        """Read subprocess stdout/stderr streams, log them, and return outputs."""
        verbose_opt = options.get("verbose", 0)
        if isinstance(verbose_opt, bool):
            verbose_level = 1 if verbose_opt else 0
        else:
            verbose_level = int(verbose_opt)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def read_stream(stream, chunks, tag, color_code, should_print):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='replace')
                chunks.append(decoded_line)
                if should_print:
                    logger.info("[%s]%s", tag, decoded_line.rstrip())

        await asyncio.gather(
            read_stream(proc.stdout, stdout_chunks, f"{prefix} OUT ", '\033[94m', verbose_level >= 1),
            read_stream(proc.stderr, stderr_chunks, f"{prefix} ERR ", '\033[93m', verbose_level >= 2)
        )

        await proc.wait()

        raw_stdout = "".join(stdout_chunks)
        raw_stderr = "".join(stderr_chunks)

        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        with open(logs_dir / "stdout.txt", "w") as f:
            f.write(raw_stdout)
        with open(logs_dir / "stderr.txt", "w") as f:
            f.write(raw_stderr)

        returncode = proc.returncode if proc.returncode is not None else 1
        return returncode, raw_stdout, raw_stderr

    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from a code fence or a loose JSON object in text."""
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end+1])
        except Exception:
            pass

        return None

    @abstractmethod
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        """Phase 1: Generate engine-specific configuration file in workspace."""
        pass

    @abstractmethod
    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path) -> Path:
        """Phase 2: Install skill to workspace and patch SKILL.md."""
        pass

    @abstractmethod
    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: Dict[str, Any]) -> str:
        """Phase 3: Resolve inputs and render invocation prompt."""
        pass

    @abstractmethod
    async def _execute_process(self, prompt: str, run_dir: Path, skill: SkillManifest, options: Dict[str, Any]) -> tuple[int, str, str]:
        """Phase 4: Execute subprocess. Returns (exit_code, stdout, stderr)."""
        pass

    @abstractmethod
    def _parse_output(self, raw_stdout: str) -> Optional[Dict[str, Any]]:
        """Phase 5: Extract structured result from raw output."""
        pass
