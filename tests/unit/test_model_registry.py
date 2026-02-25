import pytest
import json
from pathlib import Path

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

    manifest = registry._load_manifest("iflow")
    expected = max(
        (snap["version"] for snap in manifest["snapshots"]),
        key=registry._semver_key
    )
    assert catalog.snapshot_version_used == expected
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


def test_validate_model_opencode_requires_provider_model(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda engine: None)
    monkeypatch.setattr(
        "server.services.model_registry.opencode_model_catalog.get_snapshot",
        lambda: {
            "status": "ready",
            "updated_at": "2026-02-25T00:00:00Z",
            "last_error": None,
            "models": [
                {
                    "id": "openai/gpt-5",
                    "display_name": "OpenAI GPT-5",
                    "deprecated": False,
                    "notes": "seed",
                    "provider": "openai",
                    "model": "gpt-5",
                }
            ],
        },
    )

    result = registry.validate_model("opencode", "openai/gpt-5")
    assert result["model"] == "openai/gpt-5"

    with pytest.raises(ValueError, match="provider>/<model"):
        registry.validate_model("opencode", "gpt-5")


def test_validate_model_unknown_engine():
    registry = ModelRegistry()
    with pytest.raises(ValueError, match="Unknown engine"):
        registry.get_models("unknown", refresh=True)


def test_get_models_opencode_runtime_probe_cache(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: "0.1.0")
    monkeypatch.setattr(
        "server.services.model_registry.opencode_model_catalog.get_snapshot",
        lambda: {
            "status": "ready",
            "updated_at": "2026-02-25T00:00:00Z",
            "last_error": None,
            "models": [
                {
                    "id": "anthropic/claude-sonnet-4.5",
                    "display_name": "Claude Sonnet 4.5",
                    "deprecated": False,
                    "notes": "runtime_probe_cache",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4.5",
                }
            ],
        },
    )

    catalog = registry.get_models("opencode", refresh=True)
    assert catalog.source == "runtime_probe_cache"
    assert catalog.snapshot_version_used == "2026-02-25T00:00:00Z"
    assert catalog.models[0].provider == "anthropic"
    assert catalog.models[0].model == "claude-sonnet-4.5"


def test_get_manifest_view_opencode_dynamic_compat(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: "0.1.0")
    monkeypatch.setattr(
        "server.services.model_registry.opencode_model_catalog.get_snapshot",
        lambda: {
            "status": "ready",
            "updated_at": "2026-02-25T00:00:00Z",
            "last_error": None,
            "providers": ["openai"],
            "models": [
                {
                    "id": "openai/gpt-5",
                    "display_name": "OpenAI GPT-5",
                    "deprecated": False,
                    "notes": "runtime_probe_cache",
                    "provider": "openai",
                    "model": "gpt-5",
                }
            ],
        },
    )

    view = registry.get_manifest_view("opencode")
    assert view["engine"] == "opencode"
    assert view["manifest"]["source"] == "runtime_probe_cache"
    assert view["models"][0]["provider"] == "openai"
    assert view["models"][0]["model"] == "gpt-5"


def test_add_snapshot_for_detected_version_opencode_not_supported():
    registry = ModelRegistry()
    with pytest.raises(ValueError, match="does not support model snapshots"):
        registry.add_snapshot_for_detected_version("opencode", [{"id": "openai/gpt-5"}])


def _build_models_fixture(tmp_path: Path, engine: str) -> Path:
    engine_root = tmp_path / engine
    engine_root.mkdir(parents=True, exist_ok=True)
    with open(engine_root / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "engine": engine,
                "snapshots": [{"version": "0.1.0", "file": "models_0.1.0.json"}],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    with open(engine_root / "models_0.1.0.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "engine": engine,
                "version": "0.1.0",
                "models": [
                    {"id": "model-a", "display_name": "Model A", "deprecated": False, "notes": "seed"}
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return engine_root


def test_get_manifest_view(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_models_root", lambda _engine: tmp_path / "gemini")
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: "0.1.0")

    view = registry.get_manifest_view("gemini")

    assert view["engine"] == "gemini"
    assert view["resolved_snapshot_version"] == "0.1.0"
    assert view["resolved_snapshot_file"] == "models_0.1.0.json"
    assert view["models"][0]["id"] == "model-a"


def test_add_snapshot_for_detected_version_success(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    engine_root = _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_models_root", lambda _engine: engine_root)
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: "0.2.0")

    view = registry.add_snapshot_for_detected_version(
        "gemini",
        [
            {
                "id": "model-b",
                "display_name": "Model B",
                "deprecated": False,
                "notes": "new",
            }
        ],
    )

    assert view["resolved_snapshot_version"] == "0.2.0"
    assert (engine_root / "models_0.2.0.json").exists()
    with open(engine_root / "manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert any(s["version"] == "0.2.0" for s in manifest["snapshots"])


def test_add_snapshot_for_detected_version_rejects_existing(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    engine_root = _build_models_fixture(tmp_path, "gemini")
    with open(engine_root / "models_0.2.0.json", "w", encoding="utf-8") as f:
        json.dump({"engine": "gemini", "version": "0.2.0", "models": []}, f)
    monkeypatch.setattr(registry, "_models_root", lambda _engine: engine_root)
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: "0.2.0")

    with pytest.raises(ValueError, match="Snapshot already exists"):
        registry.add_snapshot_for_detected_version("gemini", [{"id": "model-c"}])


def test_add_snapshot_for_detected_version_requires_version(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    engine_root = _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_models_root", lambda _engine: engine_root)
    monkeypatch.setattr(registry, "_detect_cli_version", lambda _engine: None)

    with pytest.raises(ValueError, match="CLI version not detected"):
        registry.add_snapshot_for_detected_version("gemini", [{"id": "model-c"}])
