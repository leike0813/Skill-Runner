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
