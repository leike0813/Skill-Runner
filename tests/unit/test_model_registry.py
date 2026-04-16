import pytest
import json
from pathlib import Path

from server.services.engine_management.model_registry import ModelRegistry


def test_get_models_uses_latest_snapshot_when_version_unknown(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    catalog = registry.get_models("gemini", refresh=True)

    assert catalog.engine == "gemini"
    manifest = registry._load_manifest("gemini")
    expected = max(
        (snap["version"] for snap in manifest["snapshots"]),
        key=registry._semver_key,
    )
    assert catalog.snapshot_version_used == expected
    assert catalog.fallback_reason == "cli_version_unknown"
    assert any(model.id == "gemini-2.5-pro" for model in catalog.models)


def test_get_models_uses_exact_or_lower_version(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.25.2",
    )

    catalog = registry.get_models("gemini", refresh=True)

    assert catalog.snapshot_version_used == "0.25.2"
    assert catalog.fallback_reason is None


def test_get_models_no_semver_match(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "dev-build",
    )
    monkeypatch.setattr(
        registry,
        "_adapter_profile",
        lambda _engine: _FakeMultiProviderAdapterProfile(Path(__file__).resolve().parent / "fixtures_unused"),
    )

    tmp_root = Path(__file__).resolve().parent / "_model_registry_tmp"
    if tmp_root.exists():
        import shutil
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)
    _build_qwen_models_fixture(tmp_root)
    monkeypatch.setattr(
        registry,
        "_adapter_profile",
        lambda _engine: _FakeMultiProviderAdapterProfile(tmp_root / "qwen"),
    )

    catalog = registry.get_models("qwen", refresh=True)

    manifest = registry._load_manifest("qwen")
    expected = max(
        (snap["version"] for snap in manifest["snapshots"]),
        key=registry._semver_key
    )
    assert catalog.snapshot_version_used == expected
    assert catalog.fallback_reason == "no_semver_match"


def test_validate_model_codex_effort(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    result = registry.validate_model("codex", "gpt-5.2-codex@high")
    assert result["model"] == "gpt-5.2-codex"
    assert result["provider_id"] == "openai"
    assert result["model_reasoning_effort"] == "high"


def test_validate_model_codex_unsupported_effort(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    with pytest.raises(ValueError, match="Reasoning effort"):
        registry.validate_model("codex", "gpt-5.1-codex-mini@xhigh")


def test_validate_model_non_codex_ignores_suffix_when_effort_is_unsupported(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    result = registry.validate_model("gemini", "gemini-2.5-pro@high")
    assert result == {
        "model": "gemini-2.5-pro",
        "provider_id": "google",
    }


def test_validate_model_opencode_requires_provider_model(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_model_catalog_lifecycle.get_snapshot",
        lambda _engine: {
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
    assert result == {
        "model": "gpt-5",
        "provider_id": "openai",
        "runtime_model": "openai/gpt-5",
    }

    with pytest.raises(ValueError, match="provider_id is required"):
        registry.validate_model("opencode", "gpt-5")


def test_validate_model_unknown_engine():
    registry = ModelRegistry()
    with pytest.raises(ValueError, match="Unknown engine"):
        registry.get_models("unknown", refresh=True)


def test_get_models_opencode_runtime_probe_cache(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.1.0",
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_model_catalog_lifecycle.get_snapshot",
        lambda _engine: {
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
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.1.0",
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_model_catalog_lifecycle.get_snapshot",
        lambda _engine: {
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


def _build_qwen_models_fixture(tmp_path: Path) -> Path:
    engine_root = tmp_path / "qwen"
    engine_root.mkdir(parents=True, exist_ok=True)
    with open(engine_root / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "engine": "qwen",
                "snapshots": [{"version": "0.14.0", "file": "models_0.14.0.json"}],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    with open(engine_root / "models_0.14.0.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "engine": "qwen",
                "version": "0.14.0",
                "models": [
                    {
                        "id": "qwen-oauth/qwen-coder-plus",
                        "display_name": "Qwen OAuth",
                        "deprecated": False,
                        "notes": "fixture",
                        "provider": "qwen-oauth",
                        "provider_id": "qwen-oauth",
                        "model": "qwen-coder-plus"
                    },
                    {
                        "id": "coding-plan-china/qwen3-coder-plus",
                        "display_name": "Coding Plan China",
                        "deprecated": False,
                        "notes": "fixture",
                        "provider": "coding-plan-china",
                        "provider_id": "coding-plan-china",
                        "model": "qwen3-coder-plus"
                    },
                    {
                        "id": "coding-plan-global/qwen3-coder-plus",
                        "display_name": "Coding Plan Global",
                        "deprecated": False,
                        "notes": "fixture",
                        "provider": "coding-plan-global",
                        "provider_id": "coding-plan-global",
                        "model": "qwen3-coder-plus"
                    }
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return engine_root


class _FakeAdapterProfile:
    class _ProviderContract:
        def __init__(self) -> None:
            self.multi_provider = False
            self.canonical_provider_id = "google"

    def __init__(self, root: Path) -> None:
        self._root = root
        self.provider_contract = self._ProviderContract()

    def resolve_manifest_path(self) -> Path:
        return self._root / "manifest.json"

    def resolve_models_root(self) -> Path:
        return self._root


class _FakeMultiProviderAdapterProfile:
    class _ProviderContract:
        def __init__(self) -> None:
            self.multi_provider = True
            self.canonical_provider_id = None

    def __init__(self, root: Path) -> None:
        self._root = root
        self.provider_contract = self._ProviderContract()

    def resolve_manifest_path(self) -> Path:
        return self._root / "manifest.json"

    def resolve_models_root(self) -> Path:
        return self._root


def test_get_manifest_view(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_adapter_profile", lambda _engine: _FakeAdapterProfile(tmp_path / "gemini"))
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.1.0",
    )

    view = registry.get_manifest_view("gemini")

    assert view["engine"] == "gemini"
    assert view["resolved_snapshot_version"] == "0.1.0"
    assert view["resolved_snapshot_file"] == "models_0.1.0.json"
    assert view["models"][0]["id"] == "model-a"


def test_get_manifest_view_qwen_uses_snapshot_contract(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    _build_qwen_models_fixture(tmp_path)
    monkeypatch.setattr(
        registry,
        "_adapter_profile",
        lambda _engine: _FakeMultiProviderAdapterProfile(tmp_path / "qwen"),
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    view = registry.get_manifest_view("qwen")

    assert view["engine"] == "qwen"
    assert view["manifest"]["engine"] == "qwen"
    assert view["resolved_snapshot_file"] == "models_0.14.0.json"
    assert any(item["provider_id"] == "qwen-oauth" for item in view["models"])
    assert any(item["provider_id"] == "coding-plan-china" for item in view["models"])
    assert any(item["provider_id"] == "coding-plan-global" for item in view["models"])


def test_add_snapshot_for_detected_version_success(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    engine_root = _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_adapter_profile", lambda _engine: _FakeAdapterProfile(engine_root))
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.2.0",
    )

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
    monkeypatch.setattr(registry, "_adapter_profile", lambda _engine: _FakeAdapterProfile(engine_root))
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: "0.2.0",
    )

    with pytest.raises(ValueError, match="Snapshot already exists"):
        registry.add_snapshot_for_detected_version("gemini", [{"id": "model-c"}])


def test_add_snapshot_for_detected_version_requires_version(monkeypatch, tmp_path: Path):
    registry = ModelRegistry()
    engine_root = _build_models_fixture(tmp_path, "gemini")
    monkeypatch.setattr(registry, "_adapter_profile", lambda _engine: _FakeAdapterProfile(engine_root))
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )

    with pytest.raises(ValueError, match="CLI version not detected"):
        registry.add_snapshot_for_detected_version("gemini", [{"id": "model-c"}])


def test_claude_catalog_merges_custom_provider_models_and_marks_sources(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_custom_provider_service.list_model_entries",
        lambda engine: [
            type(
                "_Entry",
                (),
                {
                    "id": "openrouter/qwen-3",
                    "display_name": "openrouter/qwen-3",
                    "provider": "openrouter",
                    "model": "qwen-3",
                    "source": "custom_provider",
                },
            )()
        ] if engine == "claude" else [],
    )

    catalog = registry.get_models("claude", refresh=True)

    assert any(item.id == "openrouter/qwen-3" and item.source == "custom_provider" for item in catalog.models)
    official = next(item for item in catalog.models if item.source == "official")
    assert official.provider == "anthropic"
    assert official.model == official.id


def test_claude_validate_model_accepts_strict_custom_provider_spec(monkeypatch):
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_status_cache_service.get_engine_version",
        lambda _engine: None,
    )
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_custom_provider_service.list_model_entries",
        lambda engine: [
            type(
                "_Entry",
                (),
                {
                    "id": "openrouter/qwen-3",
                    "display_name": "openrouter/qwen-3",
                    "provider": "openrouter",
                    "model": "qwen-3",
                    "source": "custom_provider",
                },
            )()
        ] if engine == "claude" else [],
    )

    payload = registry.validate_model("claude", "openrouter/qwen-3")

    assert payload == {
        "model": "qwen-3",
        "provider_id": "openrouter",
        "runtime_model": "openrouter/qwen-3",
    }
