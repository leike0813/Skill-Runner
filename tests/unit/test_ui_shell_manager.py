import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from server.services.ui_shell_manager import (
    UiShellBusyError,
    UiShellManager,
    UiShellRuntimeError,
    UiShellValidationError,
)


class _FakeProfile:
    def __init__(self, data_dir: Path, mode: str = "local"):
        self.data_dir = data_dir
        self.agent_home = data_dir / "agent_home"
        self.mode = mode
        self.agent_home.mkdir(parents=True, exist_ok=True)

    def build_subprocess_env(self, base_env=None):
        return dict(base_env or os.environ)


class _FakeAgentManager:
    def __init__(self, data_dir: Path, ttyd_available: bool = True, mode: str = "local"):
        self.profile = _FakeProfile(data_dir, mode=mode)
        self._ttyd_available = ttyd_available

    def resolve_engine_command(self, _engine: str):
        return Path(sys.executable)

    def resolve_ttyd_command(self):
        if self._ttyd_available:
            return Path("/usr/bin/ttyd")
        return None


class _FakeProc:
    def __init__(self, pid: int = 23456):
        self.pid = pid
        self._exit_code: int | None = None

    def poll(self):
        return self._exit_code


class _TrustSpy:
    def __init__(self):
        self.bootstrap_calls: list[Path] = []
        self.register_calls: list[tuple[str, Path]] = []
        self.remove_calls: list[tuple[str, Path]] = []

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        self.bootstrap_calls.append(runs_parent)

    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        self.register_calls.append((engine, run_dir))

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        self.remove_calls.append((engine, run_dir))


def _new_manager(
    tmp_path: Path,
    *,
    ttyd_available: bool = True,
    mode: str = "local",
    trust_manager: _TrustSpy | None = None,
) -> UiShellManager:
    return UiShellManager(
        agent_manager=cast(Any, _FakeAgentManager(tmp_path, ttyd_available=ttyd_available, mode=mode)),
        trust_manager=cast(Any, trust_manager or _TrustSpy()),
    )


@pytest.fixture
def patch_fake_popen(monkeypatch):
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeProc()

    monkeypatch.setattr(
        "server.services.ui_shell_manager.subprocess.Popen",
        _fake_popen,
    )
    monkeypatch.setattr(
        "server.services.ui_shell_manager.UiShellManager._is_port_available",
        lambda self, host, port: True,  # noqa: ARG005
    )
    return calls


def test_ui_shell_manager_rejects_unknown_engine(tmp_path: Path, patch_fake_popen):
    manager = _new_manager(tmp_path)
    with pytest.raises(UiShellValidationError):
        manager.start_session("not-exists")


def test_ui_shell_manager_requires_ttyd(tmp_path: Path, patch_fake_popen):
    manager = _new_manager(tmp_path, ttyd_available=False)
    with pytest.raises(UiShellRuntimeError):
        manager.start_session("codex")


def test_ui_shell_manager_single_active_session_busy(tmp_path: Path, patch_fake_popen):
    manager = _new_manager(tmp_path)
    started = manager.start_session("codex")
    assert started["active"] is True
    assert started["ttyd_port"] == 7681
    with pytest.raises(UiShellBusyError):
        manager.start_session("gemini")


def test_ui_shell_manager_stop_session_sets_terminal(tmp_path: Path, patch_fake_popen, monkeypatch):
    manager = _new_manager(tmp_path)
    started = manager.start_session("codex")
    assert started["status"] == "running"
    monkeypatch.setattr(
        "server.services.ui_shell_manager.os.killpg",
        lambda _pid, _sig: None,
    )
    stopped = manager.stop_session()
    assert stopped["active"] is True
    assert stopped["terminal"] is True
    assert stopped["status"] == "terminated"


def test_ui_shell_manager_landlock_disabled_is_non_blocking(
    tmp_path: Path,
    monkeypatch,
    patch_fake_popen,
):
    manager = _new_manager(tmp_path)
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")
    started = manager.start_session("codex")
    assert started["active"] is True
    assert started["sandbox_status"] == "unsupported"
    assert "LANDLOCK" in started["sandbox_message"]


def test_ui_shell_manager_non_codex_sandbox_probe_is_non_blocking(
    tmp_path: Path,
    patch_fake_popen,
):
    manager = _new_manager(tmp_path)
    started = manager.start_session("gemini")
    assert started["active"] is True
    assert started["sandbox_status"] in {"supported", "unsupported"}
    assert started["sandbox_message"]


def test_ui_shell_manager_local_port_conflict_fallback(tmp_path: Path, patch_fake_popen, monkeypatch):
    manager = _new_manager(tmp_path, mode="local")
    monkeypatch.setattr(
        "server.services.ui_shell_manager.UiShellManager._is_port_available",
        lambda self, host, port: port == 7682,  # noqa: ARG005
    )
    started = manager.start_session("codex")
    assert started["ttyd_port"] == 7682


def test_ui_shell_manager_container_port_conflict_raises_busy(tmp_path: Path, patch_fake_popen, monkeypatch):
    manager = _new_manager(tmp_path, mode="container")
    monkeypatch.setattr(
        "server.services.ui_shell_manager.UiShellManager._is_port_available",
        lambda self, host, port: False,  # noqa: ARG005
    )
    with pytest.raises(UiShellBusyError):
        manager.start_session("codex")


def test_ui_shell_manager_start_session_injects_trust_and_ttyd_flags(
    tmp_path: Path,
    patch_fake_popen,
):
    trust_spy = _TrustSpy()
    manager = _new_manager(tmp_path, trust_manager=trust_spy)

    started = manager.start_session("codex")
    session_dir = Path(started["session_dir"])

    assert trust_spy.bootstrap_calls == [tmp_path / "ui_shell_sessions"]
    assert trust_spy.register_calls == [("codex", session_dir)]
    assert len(patch_fake_popen) == 1
    popen_args, popen_kwargs = patch_fake_popen[0]
    command = list(cast(list[str], popen_args[0]))
    assert command[0] == "/usr/bin/ttyd"
    assert "--writable" in command
    assert "-w" in command
    assert "--" in command
    assert command[command.index("-w") + 1] == str(session_dir)
    assert command[command.index("--") + 1] == sys.executable
    assert "--sandbox" in command
    assert "workspace-write" in command
    assert "--ask-for-approval" in command
    assert "never" in command
    assert "features.shell_tool=false" in command
    assert "features.unified_exec=false" in command
    assert popen_kwargs["cwd"] == str(session_dir)


def test_ui_shell_manager_start_failure_rolls_back_trust(tmp_path: Path, monkeypatch):
    trust_spy = _TrustSpy()
    manager = _new_manager(tmp_path, trust_manager=trust_spy)
    monkeypatch.setattr(
        "server.services.ui_shell_manager.UiShellManager._is_port_available",
        lambda self, host, port: True,  # noqa: ARG005
    )

    def _raise_popen(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("spawn failed")

    monkeypatch.setattr(
        "server.services.ui_shell_manager.subprocess.Popen",
        _raise_popen,
    )

    with pytest.raises(RuntimeError, match="spawn failed"):
        manager.start_session("codex")

    assert len(trust_spy.register_calls) == 1
    assert len(trust_spy.remove_calls) == 1
    reg_engine, reg_path = trust_spy.register_calls[0]
    rm_engine, rm_path = trust_spy.remove_calls[0]
    assert reg_engine == rm_engine == "codex"
    assert reg_path == rm_path


def test_ui_shell_manager_gemini_session_enforces_sandbox_and_disables_shell(
    tmp_path: Path,
    monkeypatch,
    patch_fake_popen,
):
    manager = _new_manager(tmp_path)
    monkeypatch.setattr(
        manager,
        "_probe_sandbox_status",
        lambda _engine: ("supported", "sandbox ready"),
    )
    started = manager.start_session("gemini")
    session_dir = Path(started["session_dir"])
    popen_args, popen_kwargs = patch_fake_popen[0]
    command = list(cast(list[str], popen_args[0]))
    assert "--sandbox" in command
    assert "--approval-mode" in command
    assert "default" in command
    assert "GEMINI_SANDBOX" not in popen_kwargs["env"]
    settings_path = session_dir / ".gemini" / "settings.json"
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["tools"]["sandbox"] is True
    assert payload["tools"]["autoAccept"] is False
    assert "run_shell_command" in payload["tools"]["exclude"]
    assert "ShellTool" in payload["tools"]["exclude"]
    assert payload["security"]["disableYoloMode"] is True


def test_ui_shell_manager_iflow_session_disables_shell_and_reports_non_sandbox(
    tmp_path: Path,
    patch_fake_popen,
):
    manager = _new_manager(tmp_path)
    started = manager.start_session("iflow")
    session_dir = Path(started["session_dir"])
    popen_args, popen_kwargs = patch_fake_popen[0]
    command = list(cast(list[str], popen_args[0]))
    assert "--sandbox" not in command
    assert started["sandbox_status"] == "unsupported"
    assert "runs without sandbox" in started["sandbox_message"]
    assert "IFLOW_SANDBOX" not in popen_kwargs["env"]

    settings_path = session_dir / ".iflow" / "settings.json"
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["sandbox"] is False
    assert payload["autoAccept"] is False
    assert payload["approvalMode"] == "default"
    assert "ShellTool" in payload["excludeTools"]


def test_ui_shell_manager_gemini_fallback_without_sandbox_runtime_still_disables_shell(
    tmp_path: Path,
    monkeypatch,
    patch_fake_popen,
):
    manager = _new_manager(tmp_path)
    monkeypatch.setattr(
        manager,
        "_probe_sandbox_status",
        lambda _engine: ("unsupported", "docker unavailable"),
    )
    started = manager.start_session("gemini")
    session_dir = Path(started["session_dir"])
    popen_args, _ = patch_fake_popen[0]
    command = list(cast(list[str], popen_args[0]))
    assert "--sandbox" not in command
    assert "GEMINI_SANDBOX" not in patch_fake_popen[0][1]["env"]
    settings_path = session_dir / ".gemini" / "settings.json"
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["tools"]["sandbox"] is False
    assert "run_shell_command" in payload["tools"]["exclude"]

