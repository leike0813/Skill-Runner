import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.config import config
from server.engines.claude.adapter.sandbox_probe import load_claude_sandbox_probe
from server.engines.codex.adapter.sandbox_probe import load_codex_sandbox_probe
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.agent_cli_manager import CommandResult
from server.services.engine_management.runtime_profile import RuntimeProfile


def _build_profile(tmp_path: Path) -> RuntimeProfile:
    cache_root = tmp_path / "cache"
    return RuntimeProfile(
        mode="local",
        platform="linux",
        data_dir=tmp_path / "data",
        agent_cache_root=cache_root,
        agent_home=cache_root / "agent-home",
        npm_prefix=cache_root / "npm",
        uv_cache_dir=cache_root / "uv_cache",
        uv_project_environment=cache_root / "uv_venv",
    )


def _build_windows_profile(tmp_path: Path) -> RuntimeProfile:
    cache_root = tmp_path / "cache"
    return RuntimeProfile(
        mode="local",
        platform="windows",
        data_dir=tmp_path / "data",
        agent_cache_root=cache_root,
        agent_home=cache_root / "agent-home",
        npm_prefix=cache_root / "npm",
        uv_cache_dir=cache_root / "uv_cache",
        uv_project_environment=cache_root / "uv_venv",
    )


def _install_fake_managed_claude(profile: RuntimeProfile, *, helper_mode: int = 0o644) -> Path:
    bin_dir = profile.npm_prefix / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    claude_bin = bin_dir / "claude"
    claude_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude_bin.chmod(0o755)

    package_root = (
        profile.npm_prefix
        / "lib"
        / "node_modules"
        / "@anthropic-ai"
        / "claude-code"
    )
    for relpath in ("vendor/seccomp/x64/apply-seccomp", "vendor/seccomp/arm64/apply-seccomp"):
        helper_path = package_root / relpath
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        helper_path.chmod(helper_mode)
    return package_root


def test_ensure_layout_creates_default_config_files(tmp_path):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    codex_config = manager.profile.agent_home / ".codex" / "config.toml"
    gemini_settings = manager.profile.agent_home / ".gemini" / "settings.json"
    iflow_settings = manager.profile.agent_home / ".iflow" / "settings.json"
    claude_bootstrap = manager.profile.agent_home / ".claude.json"
    claude_settings = manager.profile.agent_home / ".claude" / "settings.json"
    claude_probe = manager.profile.agent_home / ".claude" / "sandbox_probe.json"
    opencode_dir = manager.profile.agent_home / ".opencode"
    opencode_config = manager.profile.agent_home / ".config" / "opencode" / "opencode.json"
    qwen_settings = manager.profile.agent_home / ".qwen" / "settings.json"
    codex_probe = manager.profile.agent_home / ".codex" / "sandbox_probe.json"

    assert codex_config.exists()
    assert codex_probe.exists()
    assert 'cli_auth_credentials_store = "file"' in codex_config.read_text(encoding="utf-8")
    assert json.loads(gemini_settings.read_text(encoding="utf-8"))["security"]["auth"]["selectedType"] == "oauth-personal"
    iflow_payload = json.loads(iflow_settings.read_text(encoding="utf-8"))
    assert iflow_payload["selectedAuthType"] == "oauth-iflow"
    assert iflow_payload["baseUrl"] == "https://apis.iflow.cn/v1"
    assert json.loads(claude_bootstrap.read_text(encoding="utf-8"))["hasCompletedOnboarding"] is True
    assert json.loads(claude_settings.read_text(encoding="utf-8")) == {}
    assert claude_probe.exists()
    assert opencode_dir.exists()
    assert opencode_config.exists()
    assert qwen_settings.exists()
    opencode_payload = json.loads(opencode_config.read_text(encoding="utf-8"))
    qwen_payload = json.loads(qwen_settings.read_text(encoding="utf-8"))
    plugins = opencode_payload.get("plugin", [])
    assert isinstance(plugins, list)
    assert any(isinstance(item, str) and item.startswith("opencode-antigravity-auth") for item in plugins)
    assert qwen_payload["general"]["enableAutoUpdate"] is False


def test_default_bootstrap_engines_come_from_global_config(tmp_path: Path) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    assert manager.default_bootstrap_engines() == ("opencode", "codex", "gemini", "claude", "qwen")


def test_default_bootstrap_engines_respect_config_override(tmp_path: Path) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    config.defrost()
    config.SYSTEM.DEFAULT_BOOTSTRAP_ENGINES = ("claude", "gemini", "claude", "missing")
    config.freeze()
    try:
        assert manager.default_bootstrap_engines() == ("claude", "gemini")
    finally:
        config.defrost()
        config.SYSTEM.DEFAULT_BOOTSTRAP_ENGINES = ("opencode", "codex", "gemini", "claude", "qwen")
        config.freeze()


def test_collect_claude_sandbox_status_reports_missing_dependencies(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: None)
    manager.ensure_layout()

    payload = manager.collect_sandbox_status("claude")

    assert payload["declared_enabled"] is True
    assert payload["available"] is False
    assert payload["status"] == "unavailable"
    assert payload["dependency_status"] == "warning"
    assert payload["warning_code"] == "CLAUDE_SANDBOX_DEPENDENCY_MISSING"
    assert payload["missing_dependencies"] == ["bubblewrap", "socat"]


def test_collect_codex_sandbox_status_reports_disabled_by_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")

    payload = manager.collect_sandbox_status("codex")

    assert payload["declared_enabled"] is False
    assert payload["available"] is False
    assert payload["status"] == "disabled"
    assert payload["dependency_status"] == "n/a"
    assert payload["warning_code"] == "CODEX_SANDBOX_DISABLED_BY_ENV"


def test_collect_codex_sandbox_status_reports_missing_bubblewrap_dependency(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: None)

    payload = manager.collect_sandbox_status("codex")

    assert payload["declared_enabled"] is True
    assert payload["available"] is False
    assert payload["status"] == "unavailable"
    assert payload["dependency_status"] == "warning"
    assert payload["warning_code"] == "CODEX_SANDBOX_DEPENDENCY_MISSING"
    assert payload["missing_dependencies"] == ["bubblewrap"]


def test_collect_codex_sandbox_status_reports_runtime_unavailable_when_probe_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(
            returncode=1,
            stdout="",
            stderr="bwrap: setting up uid map: Permission denied",
        ),
    )

    payload = manager.collect_sandbox_status("codex")

    assert payload["declared_enabled"] is True
    assert payload["available"] is False
    assert payload["status"] == "unavailable"
    assert payload["warning_code"] == "CODEX_SANDBOX_RUNTIME_UNAVAILABLE"
    assert "uid map" in payload["message"]


def test_collect_codex_sandbox_status_reports_available_when_smoke_probe_succeeds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(returncode=0, stdout="sandbox-ok", stderr=""),
    )

    payload = manager.collect_sandbox_status("codex")

    assert payload["declared_enabled"] is True
    assert payload["available"] is True
    assert payload["status"] == "available"
    assert payload["dependency_status"] == "ready"
    assert payload["warning_code"] is None


def test_collect_claude_sandbox_status_reports_available_when_smoke_probe_succeeds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(returncode=0, stdout="sandbox-ok", stderr=""),
    )
    manager.ensure_layout()

    payload = manager.collect_sandbox_status("claude")

    assert payload["declared_enabled"] is True
    assert payload["available"] is True
    assert payload["status"] == "available"
    assert payload["dependency_status"] == "ready"
    assert payload["warning_code"] is None
    assert payload["missing_dependencies"] == []


def test_collect_claude_sandbox_status_repairs_seccomp_helpers_before_probe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    _install_fake_managed_claude(manager.profile, helper_mode=0o644)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(returncode=0, stdout="sandbox-ok", stderr=""),
    )
    manager.ensure_layout()

    payload = manager.collect_sandbox_status("claude")

    helper_paths = manager._claude_seccomp_helper_paths()  # noqa: SLF001
    assert payload["available"] is True
    assert payload["warning_code"] is None
    assert payload["dependencies"]["claude_seccomp_helper"] is True
    assert all(os.access(path, os.X_OK) for path in helper_paths)


def test_collect_claude_sandbox_status_reports_runtime_unavailable_when_probe_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(
            returncode=1,
            stdout="",
            stderr="bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted",
        ),
    )
    manager.ensure_layout()

    payload = manager.collect_sandbox_status("claude")

    assert payload["declared_enabled"] is True
    assert payload["available"] is False
    assert payload["status"] == "unavailable"
    assert payload["warning_code"] == "CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE"
    assert "Failed RTM_NEWADDR" in payload["message"]


def test_collect_claude_sandbox_status_reports_runtime_unavailable_when_seccomp_helper_cannot_be_repaired(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    _install_fake_managed_claude(manager.profile, helper_mode=0o644)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")

    original_chmod = os.chmod

    def _fake_chmod(path: str | os.PathLike[str], mode: int) -> None:
        if str(path).endswith("apply-seccomp"):
            raise PermissionError("chmod blocked")
        original_chmod(path, mode)

    monkeypatch.setattr("server.services.engine_management.agent_cli_manager.os.chmod", _fake_chmod)
    manager.ensure_layout()

    payload = manager.collect_sandbox_status("claude")

    assert payload["available"] is False
    assert payload["status"] == "unavailable"
    assert payload["warning_code"] == "CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE"
    assert "chmod blocked" in payload["message"]


def test_ensure_layout_persists_claude_sandbox_probe_sidecar(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(returncode=124, stdout="", stderr="timeout"),
    )

    manager.ensure_layout()

    persisted = load_claude_sandbox_probe(manager.profile.agent_home)
    assert persisted is not None
    assert persisted.available is False
    assert persisted.warning_code == "CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE"
    assert persisted.probe_kind == "bubblewrap_smoke"


def test_ensure_layout_persists_codex_sandbox_probe_sidecar(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(manager, "_resolve_command_any", lambda names: f"/usr/bin/{next(iter(names))}")
    monkeypatch.setattr(
        manager,
        "_run_command",
        lambda argv, timeout_sec=5: CommandResult(
            returncode=1,
            stdout="",
            stderr="bwrap: setting up uid map: Permission denied",
        ),
    )

    manager.ensure_layout()

    persisted = load_codex_sandbox_probe(manager.profile.agent_home)
    assert persisted is not None
    assert persisted.available is False
    assert persisted.warning_code == "CODEX_SANDBOX_RUNTIME_UNAVAILABLE"
    assert persisted.probe_kind == "bubblewrap_smoke"


def test_import_credentials_whitelist_only(tmp_path):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    src = tmp_path / "src"
    (src / "codex").mkdir(parents=True)
    (src / "gemini").mkdir(parents=True)
    (src / "iflow").mkdir(parents=True)
    (src / "opencode").mkdir(parents=True)
    (src / "claude").mkdir(parents=True)
    (src / "qwen").mkdir(parents=True)

    (src / "codex" / "auth.json").write_text('{"token":"x"}', encoding="utf-8")
    (src / "codex" / "config.toml").write_text("should_not_copy=true", encoding="utf-8")

    (src / "gemini" / "google_accounts.json").write_text("{}", encoding="utf-8")
    (src / "gemini" / "oauth_creds.json").write_text("{}", encoding="utf-8")
    (src / "gemini" / "settings.json").write_text('{"bad":"override"}', encoding="utf-8")

    (src / "iflow" / "iflow_accounts.json").write_text("{}", encoding="utf-8")
    (src / "iflow" / "oauth_creds.json").write_text("{}", encoding="utf-8")
    (src / "iflow" / "settings.json").write_text('{"bad":"override"}', encoding="utf-8")
    (src / "opencode" / "auth.json").write_text('{"token":"x"}', encoding="utf-8")
    (src / "opencode" / "antigravity-accounts.json").write_text('{"accounts":[]}', encoding="utf-8")
    (src / "claude" / ".credentials.json").write_text('{"claudeAiOauth":{"accessToken":"x"}}', encoding="utf-8")
    (src / "qwen" / "oauth_creds.json").write_text("{}", encoding="utf-8")

    copied = manager.import_credentials(src)
    assert copied["codex"] == ["auth.json"]
    assert copied["claude"] == [".credentials.json"]
    assert copied["gemini"] == ["google_accounts.json", "oauth_creds.json"]
    assert copied["iflow"] == ["iflow_accounts.json", "oauth_creds.json"]
    assert copied["opencode"] == ["auth.json", "antigravity-accounts.json"]
    assert copied["qwen"] == ["oauth_creds.json"]

    codex_dst = manager.profile.agent_home / ".codex"
    claude_dst = manager.profile.agent_home / ".claude"
    gemini_dst = manager.profile.agent_home / ".gemini"
    iflow_dst = manager.profile.agent_home / ".iflow"
    opencode_data_dst = manager.profile.agent_home / ".local" / "share" / "opencode"
    opencode_config_dst = manager.profile.agent_home / ".config" / "opencode"
    qwen_dst = manager.profile.agent_home / ".qwen"

    assert (codex_dst / "auth.json").exists()
    assert 'cli_auth_credentials_store = "file"' in (codex_dst / "config.toml").read_text(encoding="utf-8")

    gemini_settings = json.loads((gemini_dst / "settings.json").read_text(encoding="utf-8"))
    assert gemini_settings["security"]["auth"]["selectedType"] == "oauth-personal"
    assert (claude_dst / ".credentials.json").exists()

    iflow_settings = json.loads((iflow_dst / "settings.json").read_text(encoding="utf-8"))
    assert iflow_settings["selectedAuthType"] == "oauth-iflow"
    assert iflow_settings["baseUrl"] == "https://apis.iflow.cn/v1"
    assert (qwen_dst / "oauth_creds.json").exists()
    assert (opencode_data_dst / "auth.json").exists()
    assert (opencode_config_dst / "antigravity-accounts.json").exists()


def test_ensure_layout_migrates_legacy_iflow_settings(tmp_path):
    manager = AgentCliManager(_build_profile(tmp_path))
    iflow_dir = manager.profile.agent_home / ".iflow"
    iflow_dir.mkdir(parents=True, exist_ok=True)
    legacy = iflow_dir / "settings.json"
    legacy.write_text('{"selectedAuthType":"iflow"}', encoding="utf-8")

    manager.ensure_layout()

    payload = json.loads(legacy.read_text(encoding="utf-8"))
    assert payload["selectedAuthType"] == "oauth-iflow"
    assert payload["baseUrl"] == "https://apis.iflow.cn/v1"


def test_ensure_installed_uses_managed_presence_only(tmp_path, monkeypatch):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    calls: list[str] = []

    def _fake_global(_engine: str):
        return Path("/usr/bin/fake")

    def _fake_managed(_engine: str):
        return None

    def _fake_install(package: str):
        calls.append(package)
        from server.services.engine_management.agent_cli_manager import CommandResult
        return CommandResult(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(manager, "resolve_global_engine_command", _fake_global)
    monkeypatch.setattr(manager, "resolve_managed_engine_command", _fake_managed)
    monkeypatch.setattr(manager, "install_package", _fake_install)

    results = manager.ensure_installed()
    assert set(results.keys()) == {"codex", "opencode", "gemini", "claude", "qwen"}
    assert len(calls) == 5


def test_collect_auth_status_reports_global_fallback(tmp_path, monkeypatch):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    codex_auth = manager.profile.agent_home / ".codex" / "auth.json"
    codex_auth.write_text('{"token":"x"}', encoding="utf-8")

    monkeypatch.setattr(manager, "resolve_managed_engine_command", lambda _engine: None)
    monkeypatch.setattr(manager, "resolve_global_engine_command", lambda _engine: Path("/usr/bin/fake"))

    payload = manager.collect_auth_status()
    assert payload["codex"]["effective_path_source"] == "global"
    assert payload["codex"]["global_available"] is True
    assert payload["codex"]["managed_present"] is False


def test_collect_auth_status_opencode_ready_requires_auth_json_only(tmp_path, monkeypatch):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    (manager.profile.agent_home / ".local" / "share" / "opencode").mkdir(parents=True, exist_ok=True)
    (manager.profile.agent_home / ".local" / "share" / "opencode" / "auth.json").write_text(
        '{"token":"x"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(manager, "resolve_managed_engine_command", lambda _engine: Path("/usr/bin/fake"))
    monkeypatch.setattr(manager, "resolve_global_engine_command", lambda _engine: None)

    payload = manager.collect_auth_status()
    assert payload["opencode"]["credential_files"]["auth.json"] is True
    assert payload["opencode"]["credential_state"] == "present"


def test_probe_resume_capability_success_and_profile_mapping(tmp_path, monkeypatch):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    monkeypatch.setattr(manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/fake"))

    def _fake_run(argv: list[str], timeout_sec: int = 5) -> CommandResult:
        if argv[-1] == "--help":
            return CommandResult(returncode=0, stdout="supports --resume", stderr="")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(manager, "_run_command", _fake_run)
    capability = manager.probe_resume_capability("gemini")
    assert capability.supported is True
    profile = manager.resolve_interactive_profile("gemini", 1200)
    assert profile.reason == "resume_probe_ok"
    assert profile.session_timeout_sec == 1200


def test_probe_resume_capability_failure_keeps_resumable_profile(tmp_path, monkeypatch):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    monkeypatch.setattr(manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/fake"))

    def _fake_run(argv: list[str], timeout_sec: int = 5) -> CommandResult:
        if argv[-1] == "--help":
            return CommandResult(returncode=0, stdout="resume missing", stderr="")
        return CommandResult(returncode=1, stdout="", stderr="bad flag")

    monkeypatch.setattr(manager, "_run_command", _fake_run)
    capability = manager.probe_resume_capability("iflow")
    assert capability.supported is False
    profile = manager.resolve_interactive_profile("iflow", 900)
    assert profile.reason == "forced_resumable:resume_flag_missing"
    assert profile.session_timeout_sec == 900


def test_read_version_extracts_semver_from_prefixed_output(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    monkeypatch.setattr(manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/fake"))
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
            stdout="codex-cli 0.105.0\n",
            stderr="",
            returncode=0,
        ),
    )

    assert manager.read_version("codex") == "0.105.0"


def test_read_version_returns_none_on_oserror(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    monkeypatch.setattr(manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/fake"))

    def _raise_oserror(*_args, **_kwargs):
        raise OSError(193, "%1 is not a valid Win32 application")

    monkeypatch.setattr("subprocess.run", _raise_oserror)
    assert manager.read_version("codex") is None


def test_resolve_managed_engine_command_prefers_windows_cmd(tmp_path: Path) -> None:
    manager = AgentCliManager(_build_windows_profile(tmp_path))
    manager.ensure_layout()
    npm_prefix = manager.profile.npm_prefix
    npm_prefix.mkdir(parents=True, exist_ok=True)
    shim = npm_prefix / "codex"
    cmd = npm_prefix / "codex.cmd"
    shim.write_text("shim", encoding="utf-8")
    cmd.write_text("@echo off", encoding="utf-8")
    shim.chmod(0o755)
    cmd.chmod(0o755)
    resolved = manager.resolve_managed_engine_command("codex")
    assert resolved is not None
    assert resolved.name == "codex.cmd"


def test_resolve_ttyd_command_prefers_windows_wrappers(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_windows_profile(tmp_path))
    manager.ensure_layout()
    seen: list[str] = []

    def _fake_which(name: str, path: str | None = None):  # noqa: ARG001
        seen.append(name)
        if name == "ttyd.cmd":
            return "/tmp/ttyd.cmd"
        return None

    monkeypatch.setattr("shutil.which", _fake_which)
    resolved = manager.resolve_ttyd_command()
    assert resolved is not None
    assert resolved.name == "ttyd.cmd"
    assert seen[0] == "ttyd.cmd"


def test_run_command_returns_failure_on_oserror(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    def _raise_oserror(*_args, **_kwargs):
        raise OSError(193, "%1 is not a valid Win32 application")

    monkeypatch.setattr("subprocess.run", _raise_oserror)
    result = manager._run_command(["codex", "--help"])
    assert result.returncode == 127
    assert result.stdout == ""


def test_install_package_prefers_windows_npm_cmd(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_windows_profile(tmp_path))
    manager.ensure_layout()

    seen_names: list[str] = []

    def _fake_which(name: str, path: str | None = None):  # noqa: ARG001
        seen_names.append(name)
        if name == "npm.cmd":
            return "C:/Program Files/nodejs/npm.cmd"
        return None

    captured_cmd: list[str] = []

    def _fake_run(argv, **kwargs):  # noqa: ANN001, ANN003
        captured_cmd[:] = argv
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("shutil.which", _fake_which)
    monkeypatch.setattr("subprocess.run", _fake_run)
    result = manager.install_package("@openai/codex")

    assert seen_names[0] == "npm.cmd"
    assert captured_cmd[0].lower().endswith("npm.cmd")
    assert result.returncode == 0


def test_install_package_repairs_claude_seccomp_helper_permissions_after_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()
    package_root = _install_fake_managed_claude(manager.profile, helper_mode=0o644)
    helper_paths = sorted(package_root.glob("vendor/seccomp/*/apply-seccomp"))
    assert helper_paths
    assert all(not os.access(path, os.X_OK) for path in helper_paths)

    monkeypatch.setattr("shutil.which", lambda *args, **kwargs: "/usr/bin/npm")
    monkeypatch.setattr(
        "subprocess.run",
        lambda argv, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    result = manager.install_package("@anthropic-ai/claude-code")

    assert result.returncode == 0
    assert all(os.access(path, os.X_OK) for path in helper_paths)


def test_resolve_npm_command_prefers_explicit_env_override_on_windows(tmp_path: Path) -> None:
    manager = AgentCliManager(_build_windows_profile(tmp_path))
    manager.ensure_layout()
    explicit = str((tmp_path / "nodejs" / "npm.cmd").resolve())
    explicit_path = Path(explicit)
    explicit_path.parent.mkdir(parents=True, exist_ok=True)
    explicit_path.write_text("@echo off", encoding="utf-8")
    resolved = manager._resolve_npm_command(  # noqa: SLF001
        {
            "PATH": "",
            "SKILL_RUNNER_NPM_COMMAND": explicit,
        }
    )
    assert Path(resolved).resolve() == explicit_path.resolve()


def test_install_package_returns_failure_on_oserror(tmp_path: Path, monkeypatch) -> None:
    manager = AgentCliManager(_build_windows_profile(tmp_path))
    manager.ensure_layout()

    monkeypatch.setattr("shutil.which", lambda *args, **kwargs: "C:/Program Files/nodejs/npm.cmd")

    def _raise_oserror(*_args, **_kwargs):
        raise FileNotFoundError(2, "file not found")

    monkeypatch.setattr("subprocess.run", _raise_oserror)
    result = manager.install_package("@openai/codex")
    assert result.returncode == 127
    assert "file not found" in result.stderr.lower()


@pytest.mark.parametrize(
    ("engine", "source_name", "target_relpath"),
    [
        ("codex", "auth.json", ".codex/auth.json"),
        ("gemini", "oauth_creds.json", ".gemini/oauth_creds.json"),
        ("iflow", "iflow_accounts.json", ".iflow/iflow_accounts.json"),
        ("opencode", "auth.json", ".local/share/opencode/auth.json"),
        ("qwen", "oauth_creds.json", ".qwen/oauth_creds.json"),
    ],
)
def test_import_credentials_uses_profile_rules_for_all_engines(
    tmp_path: Path,
    engine: str,
    source_name: str,
    target_relpath: str,
) -> None:
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    source_root = tmp_path / "src"
    engine_dir = source_root / engine
    engine_dir.mkdir(parents=True, exist_ok=True)
    (engine_dir / source_name).write_text("{}", encoding="utf-8")

    copied = manager.import_credentials(source_root)
    assert source_name in copied[engine]
    assert (manager.profile.agent_home / target_relpath).exists()
