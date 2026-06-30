from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from server.engines.kilo.models.catalog_service import KiloModelCatalog
from server.services.engine_management.model_registry import ModelRegistry


def test_kilo_parse_verbose_models_keeps_executable_model_ids(tmp_path: Path) -> None:
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("kilo"))
    catalog = KiloModelCatalog(profile=profile, cli_manager=cli_manager)

    rows = catalog._parse_verbose_models(  # noqa: SLF001
        """
kilo/kilo-auto/free
kilo/kilo-auto
anthropic/claude-sonnet-4-5  Claude Sonnet 4.5
        """
    )

    assert [item["id"] for item in rows] == [
        "anthropic/claude-sonnet-4-5",
        "kilo/kilo-auto",
        "kilo/kilo-auto/free",
    ]
    assert rows[2]["provider_id"] == "kilo/kilo-auto"
    assert rows[2]["model"] == "free"


def test_kilo_parse_verbose_models_uses_label_as_canonical_id(tmp_path: Path) -> None:
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("kilo"))
    catalog = KiloModelCatalog(profile=profile, cli_manager=cli_manager)

    rows = catalog._parse_verbose_models(  # noqa: SLF001
        """
kilo/openai/gpt-5.2
{
  "id": "openai/gpt-5.2",
  "providerID": "kilo",
  "name": "OpenAI: GPT-5.2",
  "variants": {
    "low": {},
    "high": {}
  }
}
opencode-go/qwen3.7-plus
{
  "id": "qwen3.7-plus",
  "providerID": "opencode-go",
  "name": "Qwen 3.7 Plus",
  "variants": {}
}
        """
    )

    assert rows == [
        {
            "id": "kilo/openai/gpt-5.2",
            "provider": "kilo/openai",
            "provider_id": "kilo/openai",
            "model": "gpt-5.2",
            "display_name": "OpenAI: GPT-5.2",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["low", "high"],
        },
        {
            "id": "opencode-go/qwen3.7-plus",
            "provider": "opencode-go",
            "provider_id": "opencode-go",
            "model": "qwen3.7-plus",
            "display_name": "Qwen 3.7 Plus",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["default"],
        },
    ]


def test_kilo_seed_payload_is_minimal_fallback(tmp_path: Path) -> None:
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("kilo"))
    catalog = KiloModelCatalog(profile=profile, cli_manager=cli_manager)

    snapshot = catalog.get_snapshot()

    assert snapshot["models"][0]["id"] == "kilo/kilo-auto/free"
    assert snapshot["models"][0]["provider_id"] == "kilo/kilo-auto"
    assert snapshot["models"][0]["model"] == "free"


def test_kilo_model_registry_accepts_full_runtime_model_id(monkeypatch) -> None:
    registry = ModelRegistry()
    monkeypatch.setattr(
        "server.services.engine_management.model_registry.engine_model_catalog_lifecycle.get_snapshot",
        lambda _engine: {
            "status": "ready",
            "updated_at": "2026-06-29T00:00:00Z",
            "last_error": None,
            "models": [
                {
                    "id": "kilo/kilo-auto/free",
                    "display_name": "Kilo Auto Free",
                    "deprecated": False,
                    "notes": "runtime_probe_cache",
                    "provider": "kilo/kilo-auto",
                    "provider_id": "kilo/kilo-auto",
                    "model": "kilo/kilo-auto/free",
                }
            ],
        },
    )

    payload = registry.validate_model("kilo", "kilo/kilo-auto/free")

    assert payload == {
        "model": "free",
        "provider_id": "kilo/kilo-auto",
        "runtime_model": "kilo/kilo-auto/free",
    }
