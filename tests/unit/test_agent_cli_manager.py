import json
from pathlib import Path

from server.services.agent_cli_manager import AgentCliManager
from server.services.runtime_profile import RuntimeProfile


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


def test_ensure_layout_creates_default_config_files(tmp_path):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    codex_config = manager.profile.agent_home / ".codex" / "config.toml"
    gemini_settings = manager.profile.agent_home / ".gemini" / "settings.json"
    iflow_settings = manager.profile.agent_home / ".iflow" / "settings.json"

    assert codex_config.exists()
    assert 'cli_auth_credentials_store = "file"' in codex_config.read_text(encoding="utf-8")
    assert json.loads(gemini_settings.read_text(encoding="utf-8"))["security"]["auth"]["selectedType"] == "oauth-personal"
    iflow_payload = json.loads(iflow_settings.read_text(encoding="utf-8"))
    assert iflow_payload["selectedAuthType"] == "oauth-iflow"
    assert iflow_payload["baseUrl"] == "https://apis.iflow.cn/v1"


def test_import_credentials_whitelist_only(tmp_path):
    manager = AgentCliManager(_build_profile(tmp_path))
    manager.ensure_layout()

    src = tmp_path / "src"
    (src / "codex").mkdir(parents=True)
    (src / "gemini").mkdir(parents=True)
    (src / "iflow").mkdir(parents=True)

    (src / "codex" / "auth.json").write_text('{"token":"x"}', encoding="utf-8")
    (src / "codex" / "config.toml").write_text("should_not_copy=true", encoding="utf-8")

    (src / "gemini" / "google_accounts.json").write_text("{}", encoding="utf-8")
    (src / "gemini" / "oauth_creds.json").write_text("{}", encoding="utf-8")
    (src / "gemini" / "settings.json").write_text('{"bad":"override"}', encoding="utf-8")

    (src / "iflow" / "iflow_accounts.json").write_text("{}", encoding="utf-8")
    (src / "iflow" / "oauth_creds.json").write_text("{}", encoding="utf-8")
    (src / "iflow" / "settings.json").write_text('{"bad":"override"}', encoding="utf-8")

    copied = manager.import_credentials(src)
    assert copied["codex"] == ["auth.json"]
    assert copied["gemini"] == ["google_accounts.json", "oauth_creds.json"]
    assert copied["iflow"] == ["iflow_accounts.json", "oauth_creds.json"]

    codex_dst = manager.profile.agent_home / ".codex"
    gemini_dst = manager.profile.agent_home / ".gemini"
    iflow_dst = manager.profile.agent_home / ".iflow"

    assert (codex_dst / "auth.json").exists()
    assert 'cli_auth_credentials_store = "file"' in (codex_dst / "config.toml").read_text(encoding="utf-8")

    gemini_settings = json.loads((gemini_dst / "settings.json").read_text(encoding="utf-8"))
    assert gemini_settings["security"]["auth"]["selectedType"] == "oauth-personal"

    iflow_settings = json.loads((iflow_dst / "settings.json").read_text(encoding="utf-8"))
    assert iflow_settings["selectedAuthType"] == "oauth-iflow"
    assert iflow_settings["baseUrl"] == "https://apis.iflow.cn/v1"


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
        from server.services.agent_cli_manager import CommandResult
        return CommandResult(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(manager, "resolve_global_engine_command", _fake_global)
    monkeypatch.setattr(manager, "resolve_managed_engine_command", _fake_managed)
    monkeypatch.setattr(manager, "install_package", _fake_install)

    results = manager.ensure_installed()
    assert set(results.keys()) == {"codex", "gemini", "iflow"}
    assert len(calls) == 3


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
