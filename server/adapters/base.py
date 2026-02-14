from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
import asyncio
import json
import re
import logging
import os
import signal
import subprocess
from pathlib import Path
from ..models import SkillManifest
from ..config import config


AUTH_REQUIRED_PATTERNS = (
    re.compile(r"enter authorization code", re.IGNORECASE),
    re.compile(r"visit this url", re.IGNORECASE),
    re.compile(r"401\\s+unauthorized", re.IGNORECASE),
    re.compile(r"missing\\s+bearer", re.IGNORECASE),
    re.compile(r"server_oauth2_required", re.IGNORECASE),
    re.compile(r"需要使用服务器oauth2流程", re.IGNORECASE),
)


class ProcessExecutionResult:
    """Normalized process execution result from adapter subprocess."""

    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        failure_reason: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.failure_reason = failure_reason

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
        artifacts_created: List[Path] = [],
        failure_reason: Optional[str] = None,
        repair_level: str = "none",
    ):
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.output_file_path = output_file_path
        self.artifacts_created = artifacts_created
        self.failure_reason = failure_reason
        self.repair_level = repair_level

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
        process_result = await self._execute_process(prompt, run_dir, skill, options)
        exit_code = process_result.exit_code
        stdout = process_result.raw_stdout
        stderr = process_result.raw_stderr
        
        # 5. Result Parsing
        result_payload, repair_level = self._parse_output(stdout)
        
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
            artifacts_created=artifacts,
            failure_reason=process_result.failure_reason,
            repair_level=repair_level,
        )

    async def _capture_process_output(
        self,
        proc,
        run_dir: Path,
        options: Dict[str, Any],
        prefix: str,
    ) -> ProcessExecutionResult:
        """Read subprocess stdout/stderr streams, log them, and return outputs."""
        verbose_opt = options.get("verbose", 0)
        if isinstance(verbose_opt, bool):
            verbose_level = 1 if verbose_opt else 0
        else:
            verbose_level = int(verbose_opt)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = logs_dir / "stdout.txt"
        stderr_log = logs_dir / "stderr.txt"
        # Truncate old logs before streaming new output.
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text("", encoding="utf-8")

        async def read_stream(stream, chunks, log_path: Path, tag, should_print):
            with open(log_path, "a", encoding="utf-8") as log_file:
                while True:
                    chunk = await stream.read(1024)
                    if not chunk:
                        break
                    decoded_chunk = chunk.decode("utf-8", errors="replace")
                    chunks.append(decoded_chunk)
                    log_file.write(decoded_chunk)
                    log_file.flush()
                    if should_print:
                        logger.info("[%s]%s", tag, decoded_chunk.rstrip())

        stdout_task = asyncio.create_task(
            read_stream(
                proc.stdout,
                stdout_chunks,
                stdout_log,
                f"{prefix} OUT ",
                verbose_level >= 1,
            )
        )
        stderr_task = asyncio.create_task(
            read_stream(
                proc.stderr,
                stderr_chunks,
                stderr_log,
                f"{prefix} ERR ",
                verbose_level >= 2,
            )
        )
        timeout_sec = self._resolve_hard_timeout(options)
        timed_out = False
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            timed_out = True
            logger.error("[%s] hard timeout reached (%ss), terminating process", prefix, timeout_sec)
            await self._terminate_process_tree(proc, prefix)
        finally:
            try:
                await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task, return_exceptions=True),
                    timeout=5,
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] stream readers did not finish in time; cancelling", prefix)
                stdout_task.cancel()
                stderr_task.cancel()
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        raw_stdout = "".join(stdout_chunks)
        raw_stderr = "".join(stderr_chunks)

        returncode = proc.returncode if proc.returncode is not None else 1
        failure_reason: Optional[str] = None
        if self._looks_like_auth_required(raw_stdout, raw_stderr) and (timed_out or returncode != 0):
            failure_reason = "AUTH_REQUIRED"
        elif timed_out:
            failure_reason = "TIMEOUT"
        return ProcessExecutionResult(
            exit_code=returncode,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            failure_reason=failure_reason,
        )

    async def _create_subprocess(
        self,
        *cmd: str,
        cwd: Path,
        env: Dict[str, str],
    ):
        kwargs: Dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": str(cwd),
            "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        else:
            kwargs["start_new_session"] = True
        return await asyncio.create_subprocess_exec(*cmd, **kwargs)

    async def _terminate_process_tree(self, proc, prefix: str) -> None:
        if proc.returncode is not None:
            return
        if os.name == "nt":
            await self._terminate_process_tree_windows(proc, prefix)
            return
        await self._terminate_process_tree_posix(proc, prefix)

    async def _terminate_process_tree_posix(self, proc, prefix: str) -> None:
        try:
            pgid = os.getpgid(proc.pid)
        except Exception:
            pgid = None

        if pgid is not None and pgid == proc.pid:
            try:
                os.killpg(pgid, signal.SIGTERM)
                await asyncio.wait_for(proc.wait(), timeout=5)
                return
            except asyncio.TimeoutError:
                logger.warning("[%s] process group SIGTERM timeout, escalating to SIGKILL", prefix)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                    await asyncio.wait_for(proc.wait(), timeout=5)
                    return
                except Exception:
                    pass
            except ProcessLookupError:
                return
            except Exception:
                logger.warning("[%s] process group termination failed, fallback to terminate/kill", prefix, exc_info=True)
        elif pgid is not None:
            logger.warning(
                "[%s] subprocess is not process-group leader (pgid=%s,pid=%s); fallback to direct terminate",
                prefix,
                pgid,
                proc.pid,
            )

        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=3)
            except Exception:
                logger.warning("[%s] fallback terminate/kill failed", prefix, exc_info=True)

    async def _terminate_process_tree_windows(self, proc, prefix: str) -> None:
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            try:
                proc.send_signal(ctrl_break)
                await asyncio.wait_for(proc.wait(), timeout=3)
                return
            except Exception:
                pass

        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)
            return
        except Exception:
            pass

        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:
            logger.warning("[%s] windows terminate/kill failed", prefix, exc_info=True)

    def _resolve_hard_timeout(self, options: Dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return default_timeout

    def _looks_like_auth_required(self, stdout: str, stderr: str) -> bool:
        combined = f"{stdout}\n{stderr}"
        return any(pattern.search(combined) for pattern in AUTH_REQUIRED_PATTERNS)

    def _parse_json_with_deterministic_repair(self, text: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Deterministic generic repair:
        - strict parse
        - trim
        - code fence extraction
        - first JSON object extraction
        """
        parsed = self._try_parse_json_object(text)
        if parsed is not None:
            return parsed, "none"

        stripped = text.strip()
        if stripped and stripped != text:
            parsed = self._try_parse_json_object(stripped)
            if parsed is not None:
                return parsed, "deterministic_generic"

        for candidate in self._extract_code_fence_candidates(text):
            parsed = self._try_parse_json_object(candidate)
            if parsed is not None:
                return parsed, "deterministic_generic"

        first_obj = self._extract_first_json_object(text)
        if first_obj:
            parsed = self._try_parse_json_object(first_obj)
            if parsed is not None:
                return parsed, "deterministic_generic"

        if stripped and stripped != text:
            first_obj = self._extract_first_json_object(stripped)
            if first_obj:
                parsed = self._try_parse_json_object(first_obj)
                if parsed is not None:
                    return parsed, "deterministic_generic"

        return None, "none"

    def _try_parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    def _extract_code_fence_candidates(self, text: str) -> List[str]:
        candidates: List[str] = []
        patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```(?:json)?\s*(\{.*?\})\s*```",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                value = match.group(1).strip()
                if value:
                    candidates.append(value)
        return candidates

    def _extract_first_json_object(self, text: str) -> Optional[str]:
        start = -1
        depth = 0
        in_string = False
        escape = False
        for idx, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == "}":
                if depth == 0:
                    continue
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:idx + 1]
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
    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        """Phase 4: Execute subprocess."""
        pass

    @abstractmethod
    def _parse_output(self, raw_stdout: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """Phase 5: Extract structured result from raw output."""
        pass
