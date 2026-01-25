import pytest

from server.services.model_registry import ModelRegistry


def test_get_models_uses_latest_snapshot_when_version_unknown(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: None)

    catalog = registry.get_models("gemini", refresh=True)

    assert catalog.engine == "gemini"
    assert catalog.snapshot_version_used == "0.25.2"
    assert catalog.fallback_reason == "cli_version_unknown"
    assert any(model.id == "gemini-2.5-pro" for model in catalog.models)


def test_get_models_uses_exact_or_lower_version(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: "0.25.2")

    catalog = registry.get_models("gemini", refresh=True)

    assert catalog.snapshot_version_used == "0.25.2"
    assert catalog.fallback_reason is None


def test_get_models_no_semver_match(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: "dev-build")

    catalog = registry.get_models("iflow", refresh=True)

    assert catalog.snapshot_version_used == "0.5.2"
    assert catalog.fallback_reason == "no_semver_match"


def test_validate_model_codex_effort(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: None)

    result = registry.validate_model("codex", "gpt-5.2-codex@high")
    assert result["model"] == "gpt-5.2-codex"
    assert result["model_reasoning_effort"] == "high"


def test_validate_model_codex_unsupported_effort(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: None)

    with pytest.raises(ValueError, match="Reasoning effort"):
        registry.validate_model("codex", "gpt-5.1-codex-mini@xhigh")


def test_validate_model_non_codex_rejects_suffix(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: None)

    with pytest.raises(ValueError, match="does not support"):
        registry.validate_model("gemini", "gemini-2.5-pro@high")


def test_validate_model_unknown_engine():
    registry = ModelRegistry()
    with pytest.raises(ValueError, match="Unknown engine"):
        registry.get_models("unknown", refresh=True)
