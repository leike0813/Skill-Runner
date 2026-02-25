from pathlib import Path

from server.services import runtime_profile


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
