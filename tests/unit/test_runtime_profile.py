from pathlib import Path

from server.services.engine_management import runtime_profile


def test_runtime_profile_container_defaults(monkeypatch):
    monkeypatch.setenv("SKILL_RUNNER_RUNTIME_MODE", "container")
    monkeypatch.delenv("SKILL_RUNNER_AGENT_CACHE_DIR", raising=False)
    monkeypatch.delenv("SKILL_RUNNER_AGENT_HOME", raising=False)
    monkeypatch.delenv("SKILL_RUNNER_NPM_PREFIX", raising=False)
    monkeypatch.delenv("NPM_CONFIG_PREFIX", raising=False)
    monkeypatch.delenv("SKILL_RUNNER_DATA_DIR", raising=False)
    runtime_profile.reset_runtime_profile_cache()

    profile = runtime_profile.get_runtime_profile()
    assert profile.mode == "container"
    assert profile.agent_cache_root == Path("/opt/cache/skill-runner")
    assert profile.agent_home == Path("/opt/cache/skill-runner/agent-home")
    assert profile.npm_prefix == Path("/opt/cache/skill-runner/npm")


def test_runtime_profile_local_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_RUNNER_RUNTIME_MODE", "local")
    monkeypatch.setenv("SKILL_RUNNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SKILL_RUNNER_AGENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SKILL_RUNNER_AGENT_HOME", str(tmp_path / "agent-home"))
    monkeypatch.setenv("SKILL_RUNNER_NPM_PREFIX", str(tmp_path / "npm"))
    monkeypatch.setenv("ZDOTDIR", str(tmp_path / "host-zdot"))
    runtime_profile.reset_runtime_profile_cache()

    profile = runtime_profile.get_runtime_profile()
    assert profile.mode == "local"
    assert profile.data_dir == (tmp_path / "data").resolve()
    assert profile.agent_cache_root == (tmp_path / "cache").resolve()
    assert profile.agent_home == (tmp_path / "agent-home").resolve()
    assert profile.npm_prefix == (tmp_path / "npm").resolve()

    env = profile.build_subprocess_env()
    assert env["SKILL_RUNNER_AGENT_HOME"] == str(profile.agent_home)
    assert env["NPM_CONFIG_PREFIX"] == str(profile.npm_prefix)
    assert str(profile.npm_prefix) in env["PATH"]
    assert env["HOME"] == str(profile.agent_home)
    assert env["ZDOTDIR"] == str(profile.agent_home)
    assert env["XDG_CONFIG_HOME"] == str(profile.agent_home / ".config")
    assert env["XDG_DATA_HOME"] == str(profile.agent_home / ".local" / "share")
    assert env["XDG_STATE_HOME"] == str(profile.agent_home / ".local" / "state")
    assert env["XDG_CACHE_HOME"] == str(profile.agent_home / ".cache")
    assert env["ZOTERO_BRIDGE_PROFILE"] == str(
        profile.agent_cache_root / "zotero-bridge" / "bridge-profile.json"
    )
    assert env["ZOTERO_BRIDGE_BIN"] == str(profile.npm_prefix / "bin" / "zotero-bridge")
    assert env["OPENCODE_ENABLE_EXA"] == "1"


def test_runtime_profile_preserves_explicit_zotero_bridge_bin(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_RUNNER_RUNTIME_MODE", "local")
    monkeypatch.setenv("SKILL_RUNNER_AGENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SKILL_RUNNER_NPM_PREFIX", str(tmp_path / "npm"))
    runtime_profile.reset_runtime_profile_cache()

    profile = runtime_profile.get_runtime_profile()
    explicit = str(tmp_path / "custom" / "zotero-bridge")
    env = profile.build_subprocess_env({"ZOTERO_BRIDGE_BIN": explicit})

    assert env["ZOTERO_BRIDGE_BIN"] == explicit


def test_runtime_profile_windows_zotero_bridge_bin_path(tmp_path):
    profile = runtime_profile.RuntimeProfile(
        mode="local",
        platform="windows",
        data_dir=tmp_path / "data",
        agent_cache_root=tmp_path / "cache",
        agent_home=tmp_path / "cache" / "agent-home",
        npm_prefix=tmp_path / "cache" / "npm",
        uv_cache_dir=tmp_path / "cache" / "uv_cache",
        uv_project_environment=tmp_path / "cache" / "uv_venv",
    )

    env = profile.build_subprocess_env({})

    assert env["ZOTERO_BRIDGE_BIN"] == str(profile.npm_prefix / "bin" / "zotero-bridge.exe")
