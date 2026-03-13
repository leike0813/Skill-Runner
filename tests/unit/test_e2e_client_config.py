from pathlib import Path

from e2e_client.config import (
    BACKEND_BASE_URL_ENV,
    FIXTURES_SKILLS_DIR_ENV,
    PORT_ENV,
    load_settings,
)


def test_e2e_client_port_defaults_to_9814(monkeypatch):
    monkeypatch.delenv(PORT_ENV, raising=False)
    settings = load_settings()
    assert settings.port == 9814


def test_e2e_client_port_env_override_and_invalid_fallback(monkeypatch):
    monkeypatch.setenv(PORT_ENV, "9009")
    assert load_settings().port == 9009

    monkeypatch.setenv(PORT_ENV, "invalid")
    assert load_settings().port == 9814

    monkeypatch.setenv(PORT_ENV, "70000")
    assert load_settings().port == 9814


def test_e2e_client_backend_and_fixtures_env(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(BACKEND_BASE_URL_ENV, raising=False)
    settings = load_settings()
    assert settings.backend_base_url == "http://127.0.0.1:9813"

    monkeypatch.setenv(BACKEND_BASE_URL_ENV, "http://127.0.0.1:8999/")
    monkeypatch.setenv(FIXTURES_SKILLS_DIR_ENV, str(tmp_path / "fixture_skills"))
    settings = load_settings()
    assert settings.backend_base_url == "http://127.0.0.1:8999"
    assert settings.fixtures_skills_dir == tmp_path / "fixture_skills"
