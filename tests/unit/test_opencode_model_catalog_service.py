from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from server.engines.opencode.models.catalog_service import OpencodeModelCatalog


def test_probe_timeout_uses_unified_timeout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.config",
        SimpleNamespace(
            SYSTEM=SimpleNamespace(
                ROOT=str(tmp_path),
                DATA_DIR=str(tmp_path / "data"),
                ENGINE_MODELS_CATALOG_CACHE_DIR=str(tmp_path / "cache"),
                ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE="{engine}.json",
                ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC=20,
            )
        ),
    )
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("opencode"))
    catalog = OpencodeModelCatalog(profile=profile, cli_manager=cli_manager)

    assert catalog._resolve_probe_timeout_seconds() == 20  # noqa: SLF001


def test_parse_verbose_models_extracts_provider_model_and_supported_effort(tmp_path: Path) -> None:
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("opencode"))
    catalog = OpencodeModelCatalog(profile=profile, cli_manager=cli_manager)

    rows = catalog._parse_verbose_models(  # noqa: SLF001
        """
        {
          "models": [
            {
              "id": "openai/gpt-5",
              "name": "OpenAI GPT-5",
              "variants": {
                "low": {},
                "medium": {},
                "high": {}
              }
            },
            {
              "provider": "anthropic",
              "model": "claude-sonnet-4-5",
              "display_name": "Claude Sonnet 4.5"
            }
          ]
        }
        """
    )

    assert rows == [
        {
            "id": "anthropic/claude-sonnet-4-5",
            "provider": "anthropic",
            "provider_id": "anthropic",
            "model": "claude-sonnet-4-5",
            "display_name": "Claude Sonnet 4.5",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["default"],
        },
        {
            "id": "openai/gpt-5",
            "provider": "openai",
            "provider_id": "openai",
            "model": "gpt-5",
            "display_name": "OpenAI GPT-5",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["low", "medium", "high"],
        },
    ]


def test_parse_verbose_models_accepts_label_plus_json_blocks(tmp_path: Path) -> None:
    profile = SimpleNamespace(build_subprocess_env=lambda: {}, data_dir=tmp_path / "data")
    cli_manager = SimpleNamespace(resolve_engine_command=lambda _engine: Path("opencode"))
    catalog = OpencodeModelCatalog(profile=profile, cli_manager=cli_manager)

    rows = catalog._parse_verbose_models(  # noqa: SLF001
        """
opencode/big-pickle
{
  "id": "big-pickle",
  "providerID": "opencode",
  "name": "Big Pickle",
  "variants": {
    "high": {},
    "max": {}
  }
}
opencode/claude-3-5-haiku
{
  "id": "claude-3-5-haiku",
  "providerID": "opencode",
  "name": "Claude Haiku 3.5",
  "variants": {}
}
        """
    )

    assert rows == [
        {
            "id": "opencode/big-pickle",
            "provider": "opencode",
            "provider_id": "opencode",
            "model": "big-pickle",
            "display_name": "Big Pickle",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["high", "max"],
        },
        {
            "id": "opencode/claude-3-5-haiku",
            "provider": "opencode",
            "provider_id": "opencode",
            "model": "claude-3-5-haiku",
            "display_name": "Claude Haiku 3.5",
            "deprecated": False,
            "notes": "runtime_probe_cache",
            "supported_effort": ["default"],
        },
    ]
