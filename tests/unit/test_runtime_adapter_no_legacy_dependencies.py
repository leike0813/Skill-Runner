from __future__ import annotations

from pathlib import Path


def test_legacy_adapter_files_removed() -> None:
    assert not Path("server/adapters/base.py").exists()
    for engine in ("codex", "gemini", "iflow", "opencode"):
        assert not Path(f"server/engines/{engine}/adapter/adapter.py").exists()
        assert not Path(f"server/engines/{engine}/adapter/entry.py").exists()
        assert not Path(f"server/engines/{engine}/adapter/prompt_builder.py").exists()
        assert not Path(f"server/engines/{engine}/adapter/session_codec.py").exists()
        assert not Path(f"server/engines/{engine}/adapter/workspace_provisioner.py").exists()


def test_no_server_module_imports_legacy_base() -> None:
    for file_path in Path("server").rglob("*.py"):
        text = file_path.read_text(encoding="utf-8")
        assert "server.adapters.base" not in text
        assert "..adapters.base" not in text
