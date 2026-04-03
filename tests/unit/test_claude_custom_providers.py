from __future__ import annotations

import json
from pathlib import Path

from server.engines.claude.custom_providers import ClaudeCustomProviderStore


def test_claude_custom_provider_store_upsert_list_resolve_and_delete(tmp_path: Path) -> None:
    config_path = tmp_path / ".claude" / "custom_providers.json"
    store = ClaudeCustomProviderStore(config_path=config_path)

    created = store.upsert_provider(
        provider_id="OpenRouter",
        api_key="sk-test",
        base_url="https://openrouter.example/v1",
        models=["qwen-3", "qwen-3-plus", "qwen-3"],
    )

    assert created.provider_id == "openrouter"
    assert created.models == ("qwen-3", "qwen-3-plus")
    listed = store.list_providers()
    assert [item.provider_id for item in listed] == ["openrouter"]
    resolved = store.resolve_model("openrouter/qwen-3")
    assert resolved is not None
    assert resolved.provider_id == "openrouter"
    assert resolved.model == "qwen-3"
    assert store.delete_provider("openrouter") is True
    assert store.list_providers() == []


def test_claude_custom_provider_store_repairs_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / ".claude" / "custom_providers.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{invalid", encoding="utf-8")
    store = ClaudeCustomProviderStore(config_path=config_path)

    providers = store.list_providers()

    assert providers == []
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload == {"providers": []}
    backups = list(config_path.parent.glob("custom_providers.json.invalid.bak*"))
    assert backups
