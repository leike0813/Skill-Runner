from __future__ import annotations

import json
from pathlib import Path

from agent_harness import cli
from agent_harness.config import HarnessConfig
from server.services.runtime_profile import RuntimeProfile


def _profile(root: Path) -> RuntimeProfile:
    return RuntimeProfile(
        mode="local",
        platform="linux",
        data_dir=root / "data",
        agent_cache_root=root / "cache",
        agent_home=root / "cache" / "agent-home",
        npm_prefix=root / "cache" / "npm",
        uv_cache_dir=root / "cache" / "uv-cache",
        uv_project_environment=root / "cache" / "uv-venv",
    )


def test_cli_start_forwards_passthrough_without_translate(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    class _FakeRuntime:
        def __init__(self, config: HarnessConfig) -> None:
            calls["config"] = config

        def start(self, request):
            calls["start"] = request
            return {
                "ok": True,
                "run_id": "run-1",
                "run_dir": "/tmp/run-1",
                "handle": None,
                "session_id": None,
                "status": "waiting_user",
                "translate_level": request.translate_level,
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
                "exit_code": 0,
                "audit": {"meta": "/tmp/run-1/.audit/meta.1.json"},
                "view": {"stdout": "", "stderr": ""},
            }

    monkeypatch.setattr(cli, "HarnessRuntime", _FakeRuntime)
    monkeypatch.setattr(
        cli,
        "resolve_harness_config",
        lambda: HarnessConfig(runtime_profile=_profile(tmp_path), run_root=tmp_path / "runs"),
    )

    exit_code = cli.main(
        ["start", "--translate", "2", "--run-dir", "reuse", "codex", "--", "--json", "--full-auto"]
    )
    captured = capsys.readouterr()
    request = calls["start"]

    assert exit_code == 0
    assert getattr(request, "translate_level") == 2
    assert getattr(request, "run_selector") == "reuse"
    assert getattr(request, "execution_mode") == "interactive"
    assert getattr(request, "passthrough_args") == ["--json", "--full-auto"]
    assert "Run id: run-1" in captured.out
    assert "Start complete. exitCode=0" in captured.out


def test_cli_resume_joins_message_tokens(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    class _FakeRuntime:
        def __init__(self, config: HarnessConfig) -> None:
            calls["config"] = config

        def resume(self, request):
            calls["resume"] = request
            return {
                "ok": True,
                "run_id": "run-2",
                "run_dir": "/tmp/run-2",
                "handle": "deadbeef",
                "session_id": "sess-1",
                "status": "waiting_user",
                "translate_level": request.translate_level,
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
                "exit_code": 0,
                "audit": {"meta": "/tmp/run-2/.audit/meta.2.json"},
                "view": "### Simulated Frontend View (Markdown)\n- System: (请输入下一步指令...)\n",
            }

    monkeypatch.setattr(cli, "HarnessRuntime", _FakeRuntime)
    monkeypatch.setattr(
        cli,
        "resolve_harness_config",
        lambda: HarnessConfig(runtime_profile=_profile(tmp_path), run_root=tmp_path / "runs"),
    )

    exit_code = cli.main(["resume", "--translate", "3", "deadbeef", "hello", "world"])
    captured = capsys.readouterr()
    request = calls["resume"]

    assert exit_code == 0
    assert getattr(request, "handle") == "deadbeef"
    assert getattr(request, "message") == "hello world"
    assert getattr(request, "translate_level") == 3
    assert "[agent-harness] ---------------- translated output begin ----------------" not in captured.out
    assert "Session: session_id=sess-1" in captured.out
    assert "Resume complete. exitCode=0" in captured.out


def test_cli_direct_engine_syntax_forwards_passthrough(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    class _FakeRuntime:
        def __init__(self, config: HarnessConfig) -> None:
            calls["config"] = config

        def start(self, request):
            calls["start"] = request
            return {
                "ok": True,
                "run_id": "run-3",
                "run_dir": "/tmp/run-3",
                "handle": None,
                "session_id": None,
                "status": "waiting_user",
                "translate_level": request.translate_level,
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
                "exit_code": 0,
                "audit": {"meta": "/tmp/run-3/.audit/meta.1.json"},
                "view": {"stdout": "", "stderr": ""},
            }

    monkeypatch.setattr(cli, "HarnessRuntime", _FakeRuntime)
    monkeypatch.setattr(
        cli,
        "resolve_harness_config",
        lambda: HarnessConfig(runtime_profile=_profile(tmp_path), run_root=tmp_path / "runs"),
    )

    exit_code = cli.main(["codex", "exec", "--json", "--full-auto", "-p", "Hello."])
    captured = capsys.readouterr()
    request = calls["start"]

    assert exit_code == 0
    assert getattr(request, "engine") == "codex"
    assert getattr(request, "execution_mode") == "interactive"
    assert getattr(request, "passthrough_args") == ["exec", "--json", "--full-auto", "-p", "Hello."]
    assert "Run id: run-3" in captured.out
    assert "Start complete. exitCode=0" in captured.out


def test_cli_direct_engine_without_passthrough_is_valid(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    class _FakeRuntime:
        def __init__(self, config: HarnessConfig) -> None:
            calls["config"] = config

        def start(self, request):
            calls["start"] = request
            return {
                "ok": True,
                "run_id": "run-4",
                "run_dir": "/tmp/run-4",
                "handle": None,
                "session_id": None,
                "status": "waiting_user",
                "translate_level": request.translate_level,
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
                "exit_code": 0,
                "audit": {"meta": "/tmp/run-4/.audit/meta.1.json"},
                "view": {"stdout": "", "stderr": ""},
            }

    monkeypatch.setattr(cli, "HarnessRuntime", _FakeRuntime)
    monkeypatch.setattr(
        cli,
        "resolve_harness_config",
        lambda: HarnessConfig(runtime_profile=_profile(tmp_path), run_root=tmp_path / "runs"),
    )

    exit_code = cli.main(["codex"])
    captured = capsys.readouterr()
    request = calls["start"]

    assert exit_code == 0
    assert getattr(request, "engine") == "codex"
    assert getattr(request, "execution_mode") == "interactive"
    assert getattr(request, "passthrough_args") == []
    assert "Run id: run-4" in captured.out
    assert "Start complete. exitCode=0" in captured.out


def test_cli_start_auto_flag_switches_to_auto_mode(monkeypatch, tmp_path, capsys) -> None:
    calls: dict[str, object] = {}

    class _FakeRuntime:
        def __init__(self, config: HarnessConfig) -> None:
            calls["config"] = config

        def start(self, request):
            calls["start"] = request
            return {
                "ok": True,
                "run_id": "run-5",
                "run_dir": "/tmp/run-5",
                "handle": None,
                "session_id": None,
                "status": "waiting_user",
                "translate_level": request.translate_level,
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
                "exit_code": 0,
                "audit": {"meta": "/tmp/run-5/.audit/meta.1.json"},
                "view": {"stdout": "", "stderr": ""},
            }

    monkeypatch.setattr(cli, "HarnessRuntime", _FakeRuntime)
    monkeypatch.setattr(
        cli,
        "resolve_harness_config",
        lambda: HarnessConfig(runtime_profile=_profile(tmp_path), run_root=tmp_path / "runs"),
    )

    exit_code = cli.main(["start", "--auto", "codex", "--", "--json"])
    captured = capsys.readouterr()
    request = calls["start"]

    assert exit_code == 0
    assert getattr(request, "execution_mode") == "auto"
    assert getattr(request, "passthrough_args") == ["--json"]
    assert "Run id: run-5" in captured.out
