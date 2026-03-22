import asyncio
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from server.config import config
from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.runtime.adapter.base_execution_adapter import (
    RUNTIME_DEPENDENCIES_INJECTION_FAILED,
    EngineExecutionAdapter,
)
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.runtime.adapter.types import ProcessExecutionResult


class _NoopComposer:
    def compose(self, ctx: AdapterExecutionContext) -> Path:  # noqa: ARG002
        return ctx.run_dir / "dummy.json"


class _NoopRunFolderValidator:
    def validate(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:  # noqa: ARG002
        return ctx.run_dir


class _NoopPromptBuilder:
    def render(self, ctx: AdapterExecutionContext) -> str:  # noqa: ARG002
        return "noop"


class _NoopCommandBuilder:
    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:  # noqa: ARG002
        return list(ctx.options.get("command", []))

    def build_resume(
        self,
        ctx: AdapterExecutionContext,  # noqa: ARG002
        prompt: str,  # noqa: ARG002
        session_handle: EngineSessionHandle,  # noqa: ARG002
    ) -> list[str]:
        return list(ctx.options.get("command", []))


class _NoopStreamParser:
    def parse(self, raw_stdout: str):  # noqa: ANN001
        return {"turn_result": {"outcome": "final", "final_data": {}, "repair_level": "none"}}

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> dict[str, object]:
        combined = "\n".join(
            part.decode("utf-8", errors="replace")
            for part in (stdout_raw, stderr_raw, pty_raw)
            if part
        )
        if "SERVER_OAUTH2_REQUIRED" in combined:
            return {
                "parser": "test_noop",
                "confidence": 0.9,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": [],
                "auth_signal": {
                    "required": True,
                    "confidence": "high",
                    "subcategory": "oauth_reauth",
                    "matched_pattern_id": "test_server_oauth2_required",
                },
            }
        if "LOW_AUTH_FALLBACK" in combined:
            return {
                "parser": "test_noop",
                "confidence": 0.4,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": [],
                "auth_signal": {
                    "required": True,
                    "confidence": "low",
                    "subcategory": None,
                    "matched_pattern_id": "generic_token_expired_text_fallback",
                },
            }
        return {
            "parser": "test_noop",
            "confidence": 0.3,
            "session_id": None,
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": [],
            "structured_types": [],
        }


class _NoopSessionCodec:
    def extract(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:  # noqa: ARG002
        return EngineSessionHandle(
            engine="test",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="dummy",
            created_at_turn=turn_index,
        )


class _TrackingRunFolderValidator:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path]] = []

    def validate(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:
        self.calls.append((ctx.run_dir, config_path))
        return ctx.run_dir


class _TestAdapter(EngineExecutionAdapter):
    def __init__(self) -> None:
        super().__init__(
            config_composer=_NoopComposer(),
            run_folder_validator=_NoopRunFolderValidator(),
            prompt_builder=_NoopPromptBuilder(),
            command_builder=_NoopCommandBuilder(),
            stream_parser=_NoopStreamParser(),
            session_codec=_NoopSessionCodec(),
            process_prefix="Test",
        )

    async def _execute_process(self, prompt: str, run_dir: Path, skill: SkillManifest, options) -> ProcessExecutionResult:
        _ = prompt, skill
        proc = await self._create_subprocess(
            *options["command"],
            cwd=run_dir,
            env=os.environ.copy(),
        )
        return await self._capture_process_output(proc, run_dir, options, "Test")


@pytest.mark.asyncio
async def test_capture_process_output_timeout_classified(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "command": ["python", "-c", "import time; time.sleep(2)"],
            "hard_timeout_seconds": 1,
        },
    )
    assert result.failure_reason == "TIMEOUT"
    assert result.exit_code != 0


@pytest.mark.asyncio
async def test_capture_process_output_auth_required_classified(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "__engine_name": "iflow",
            "command": ["python", "-c", "import sys; sys.stderr.write('SERVER_OAUTH2_REQUIRED'); sys.exit(1)"],
            "hard_timeout_seconds": 10,
        },
    )
    assert result.failure_reason == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_capture_process_output_low_confidence_auth_does_not_override_nonzero_exit(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "__engine_name": "opencode",
            "command": ["python", "-c", "import sys; sys.stderr.write('LOW_AUTH_FALLBACK'); sys.exit(1)"],
            "hard_timeout_seconds": 10,
        },
    )
    assert result.exit_code == 1
    assert result.failure_reason is None
    assert result.auth_signal_snapshot is not None
    assert result.auth_signal_snapshot["confidence"] == "low"


@pytest.mark.asyncio
async def test_capture_process_output_auth_required_early_exit_on_blocking_idle(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    old_idle_grace = config.SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS
    config.defrost()
    config.SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS = 0.4
    config.freeze()
    try:
        start = time.monotonic()
        result = await adapter._execute_process(
            "noop",
            run_dir,
            SkillManifest(id="x"),
            {
                "__engine_name": "iflow",
                "command": [
                    "python",
                    "-c",
                    "import sys,time; sys.stdout.write('SERVER_OAUTH2_REQUIRED\\n'); sys.stdout.flush(); time.sleep(60)",
                ],
                "hard_timeout_seconds": 30,
            },
        )
        elapsed = time.monotonic() - start
        assert result.failure_reason == "AUTH_REQUIRED"
        assert elapsed < 10
    finally:
        config.defrost()
        config.SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS = old_idle_grace
        config.freeze()


@pytest.mark.asyncio
async def test_capture_process_output_stream_writes_logs_during_run(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        "import sys,time;sys.stdout.write('tick\\n');sys.stdout.flush();time.sleep(1);sys.stdout.write('done\\n');sys.stdout.flush()",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(run_dir),
    )
    task = asyncio.create_task(adapter._capture_process_output(proc, run_dir, {"hard_timeout_seconds": 10}, "Test"))
    await asyncio.sleep(0.2)
    stdout_log = run_dir / ".audit" / "stdout.1.log"
    assert stdout_log.exists()
    partial = stdout_log.read_text(encoding="utf-8")
    assert "tick" in partial
    result = await task
    assert "done" in result.raw_stdout


@pytest.mark.asyncio
async def test_timeout_terminates_process_group_and_returns_promptly(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "command": [
                "python",
                "-c",
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']);"
                "print('parent-start', flush=True);"
                "time.sleep(120)",
            ],
            "hard_timeout_seconds": 1,
        },
    )
    elapsed = time.monotonic() - start
    assert result.failure_reason == "TIMEOUT"
    assert elapsed < 20


@pytest.mark.asyncio
async def test_auth_completed_resume_revalidates_run_folder_before_execute(tmp_path: Path):
    validator = _TrackingRunFolderValidator()
    adapter = EngineExecutionAdapter(
        config_composer=_NoopComposer(),
        run_folder_validator=validator,
        prompt_builder=_NoopPromptBuilder(),
        command_builder=_NoopCommandBuilder(),
        stream_parser=_NoopStreamParser(),
        session_codec=_NoopSessionCodec(),
        process_prefix="Test",
    )
    adapter._execute_process = AsyncMock(  # type: ignore[method-assign]
        return_value=ProcessExecutionResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
        )
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    await adapter.run(
        SkillManifest(id="x", path=run_dir),
        input_data={},
        run_dir=run_dir,
        options={
            "__resume_ticket_id": "ticket-1",
            "__resume_cause": "auth_completed",
        },
    )

    assert validator.calls == [(run_dir, run_dir / "dummy.json")]


@pytest.mark.asyncio
async def test_runtime_dependencies_probe_success_wraps_command(tmp_path: Path):
    adapter = EngineExecutionAdapter(
        config_composer=_NoopComposer(),
        run_folder_validator=_NoopRunFolderValidator(),
        prompt_builder=_NoopPromptBuilder(),
        command_builder=_NoopCommandBuilder(),
        stream_parser=_NoopStreamParser(),
        session_codec=_NoopSessionCodec(),
        process_prefix="Test",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    async def _fake_probe(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return True, None

    async def _fake_create_subprocess(*cmd: str, cwd: Path, env: dict[str, str]):  # type: ignore[no-untyped-def]
        _ = cwd, env
        captured["cmd"] = list(cmd)
        return object()

    async def _fake_capture_process_output(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return ProcessExecutionResult(exit_code=0, raw_stdout="", raw_stderr="")

    adapter.build_start_command = lambda **kwargs: ["python", "-c", "print('ok')"]  # type: ignore[method-assign]
    adapter._probe_uv_dependency_injection = _fake_probe  # type: ignore[method-assign]
    adapter._create_subprocess = _fake_create_subprocess  # type: ignore[method-assign]
    adapter._capture_process_output = _fake_capture_process_output  # type: ignore[method-assign]

    skill = SkillManifest(
        id="x",
        runtime={"language": "python", "version": "3.11", "dependencies": ["pymupdf4llm"]},
    )
    result = await adapter._execute_process(
        "noop",
        run_dir,
        skill,
        {},
    )
    assert result.runtime_warnings == []
    assert captured["cmd"] == [
        "uv",
        "run",
        "--with",
        "pymupdf4llm",
        "--",
        "python",
        "-c",
        "print('ok')",
    ]


@pytest.mark.asyncio
async def test_runtime_dependencies_probe_success_wraps_normalized_command(tmp_path: Path):
    adapter = EngineExecutionAdapter(
        config_composer=_NoopComposer(),
        run_folder_validator=_NoopRunFolderValidator(),
        prompt_builder=_NoopPromptBuilder(),
        command_builder=_NoopCommandBuilder(),
        stream_parser=_NoopStreamParser(),
        session_codec=_NoopSessionCodec(),
        process_prefix="Test",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    async def _fake_probe(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return True, None

    async def _fake_create_subprocess(*cmd: str, cwd: Path, env: dict[str, str]):  # type: ignore[no-untyped-def]
        _ = cwd, env
        captured["cmd"] = list(cmd)
        return object()

    async def _fake_capture_process_output(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return ProcessExecutionResult(exit_code=0, raw_stdout="", raw_stderr="")

    def _fake_normalize(command: list[str], *, env: dict[str, str]) -> tuple[list[str], bool, str]:
        _ = command, env
        return ["node", "entry.js", "run", "--format", "json", "prompt payload"], True, "npm_cmd_shim_rewritten"

    adapter.build_start_command = lambda **kwargs: [  # type: ignore[method-assign]
        r"C:\Users\runner\AppData\Local\SkillRunner\agent-cache\npm\opencode.cmd",
        "run",
        "--format",
        "json",
        "prompt payload",
    ]
    adapter._normalize_windows_npm_cmd_shim = _fake_normalize  # type: ignore[method-assign]
    adapter._probe_uv_dependency_injection = _fake_probe  # type: ignore[method-assign]
    adapter._create_subprocess = _fake_create_subprocess  # type: ignore[method-assign]
    adapter._capture_process_output = _fake_capture_process_output  # type: ignore[method-assign]

    skill = SkillManifest(
        id="x",
        runtime={"language": "python", "version": "3.11", "dependencies": ["pymupdf4llm"]},
    )
    result = await adapter._execute_process(
        "noop",
        run_dir,
        skill,
        {},
    )

    assert result.runtime_warnings == []
    assert captured["cmd"] == [
        "uv",
        "run",
        "--with",
        "pymupdf4llm",
        "--",
        "node",
        "entry.js",
        "run",
        "--format",
        "json",
        "prompt payload",
    ]
    assert all(not str(token).lower().endswith(".cmd") for token in captured["cmd"])


@pytest.mark.asyncio
async def test_runtime_dependencies_probe_failure_falls_back_and_warns(tmp_path: Path):
    adapter = EngineExecutionAdapter(
        config_composer=_NoopComposer(),
        run_folder_validator=_NoopRunFolderValidator(),
        prompt_builder=_NoopPromptBuilder(),
        command_builder=_NoopCommandBuilder(),
        stream_parser=_NoopStreamParser(),
        session_codec=_NoopSessionCodec(),
        process_prefix="Test",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    async def _fake_probe(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return False, "network unavailable"

    async def _fake_create_subprocess(*cmd: str, cwd: Path, env: dict[str, str]):  # type: ignore[no-untyped-def]
        _ = cwd, env
        captured["cmd"] = list(cmd)
        return object()

    async def _fake_capture_process_output(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return ProcessExecutionResult(exit_code=0, raw_stdout="", raw_stderr="")

    adapter.build_start_command = lambda **kwargs: ["python", "-c", "print('ok')"]  # type: ignore[method-assign]
    adapter._probe_uv_dependency_injection = _fake_probe  # type: ignore[method-assign]
    adapter._create_subprocess = _fake_create_subprocess  # type: ignore[method-assign]
    adapter._capture_process_output = _fake_capture_process_output  # type: ignore[method-assign]

    skill = SkillManifest(
        id="x",
        runtime={"language": "python", "version": "3.11", "dependencies": ["pymupdf4llm"]},
    )
    result = await adapter._execute_process(
        "noop",
        run_dir,
        skill,
        {},
    )
    assert captured["cmd"] == ["python", "-c", "print('ok')"]
    assert len(result.runtime_warnings) == 1
    assert result.runtime_warnings[0]["code"] == RUNTIME_DEPENDENCIES_INJECTION_FAILED


@pytest.mark.parametrize(
    ("shim_name", "shim_line", "expected_entry_suffix", "expected_fixed_args"),
    [
        (
            "opencode.cmd",
            'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\opencode-ai\\bin\\opencode" %*',
            "node_modules/opencode-ai/bin/opencode",
            [],
        ),
        (
            "codex.cmd",
            'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\@openai\\codex\\bin\\codex.js" %*',
            "node_modules/@openai/codex/bin/codex.js",
            [],
        ),
        (
            "gemini.cmd",
            'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%" --no-warnings=DEP0040 "%dp0%\\node_modules\\@google\\gemini-cli\\dist\\index.js" %*',
            "node_modules/@google/gemini-cli/dist/index.js",
            ["--no-warnings=DEP0040"],
        ),
        (
            "iflow.cmd",
            'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\@iflow-ai\\iflow-cli\\bundle\\entry.js" %*',
            "node_modules/@iflow-ai/iflow-cli/bundle/entry.js",
            [],
        ),
    ],
)
def test_normalize_windows_npm_cmd_shim_rewrites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shim_name: str,
    shim_line: str,
    expected_entry_suffix: str,
    expected_fixed_args: list[str],
):
    adapter = EngineExecutionAdapter()
    monkeypatch.setattr(adapter, "_is_windows_runtime", lambda: True)

    shim_dir = tmp_path / "npm"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_path = shim_dir / shim_name
    shim_path.write_text(
        "@ECHO off\nGOTO start\n:start\nSETLOCAL\n" + shim_line + "\n",
        encoding="utf-8",
    )

    command = [str(shim_path), "run", "--format", "json", "prompt payload"]
    normalized, applied, reason = adapter._normalize_windows_npm_cmd_shim(
        command,
        env={"PATH": str(shim_dir)},
    )

    assert applied is True
    assert reason == "npm_cmd_shim_rewritten"
    assert normalized[0] == "node"
    assert normalized[1].replace("\\", "/").endswith(expected_entry_suffix)
    assert normalized[2 : 2 + len(expected_fixed_args)] == expected_fixed_args
    assert normalized[2 + len(expected_fixed_args) :] == command[1:]


def test_normalize_windows_npm_cmd_shim_non_windows_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    adapter = EngineExecutionAdapter()
    monkeypatch.setattr(adapter, "_is_windows_runtime", lambda: False)
    shim_path = tmp_path / "opencode.cmd"
    shim_path.write_text("not-used", encoding="utf-8")
    command = [str(shim_path), "run", "prompt"]

    normalized, applied, reason = adapter._normalize_windows_npm_cmd_shim(
        command,
        env={"PATH": str(tmp_path)},
    )

    assert normalized == command
    assert applied is False
    assert reason == "not_applicable"


def test_normalize_windows_npm_cmd_shim_parse_failure_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    adapter = EngineExecutionAdapter()
    monkeypatch.setattr(adapter, "_is_windows_runtime", lambda: True)
    shim_dir = tmp_path / "npm"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_path = shim_dir / "broken.cmd"
    shim_path.write_text("@ECHO off\nREM not npm shim\n", encoding="utf-8")
    command = [str(shim_path), "run", "prompt"]

    normalized, applied, reason = adapter._normalize_windows_npm_cmd_shim(
        command,
        env={"PATH": str(shim_dir)},
    )

    assert normalized == command
    assert applied is False
    assert reason == "parse_failed_fallback"
