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


def test_claude_custom_provider_store_resolves_explicit_1m_variant_and_returns_base_model(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".claude" / "custom_providers.json"
    store = ClaudeCustomProviderStore(config_path=config_path)

    store.upsert_provider(
        provider_id="bailian",
        api_key="sk-test",
        base_url="https://bailian.example/v1",
        models=["qwen3.6-plus[1m]"],
    )

    resolved = store.resolve_model("bailian/qwen3.6-plus[1m]")

    assert resolved is not None
    assert resolved.provider_id == "bailian"
    assert resolved.model == "qwen3.6-plus"
    assert store.list_providers()[0].models == ("qwen3.6-plus[1m]",)


def test_claude_custom_provider_store_allows_1m_request_to_match_legacy_base_model(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".claude" / "custom_providers.json"
    store = ClaudeCustomProviderStore(config_path=config_path)

    store.upsert_provider(
        provider_id="bailian",
        api_key="sk-test",
        base_url="https://bailian.example/v1",
        models=["qwen3.6-plus"],
    )

    resolved = store.resolve_model("bailian/qwen3.6-plus[1m]")

    assert resolved is not None
    assert resolved.model == "qwen3.6-plus"


def test_claude_custom_provider_store_does_not_match_base_request_to_1m_only_model(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".claude" / "custom_providers.json"
    store = ClaudeCustomProviderStore(config_path=config_path)

    store.upsert_provider(
        provider_id="bailian",
        api_key="sk-test",
        base_url="https://bailian.example/v1",
        models=["qwen3.6-plus[1m]"],
    )

    assert store.resolve_model("bailian/qwen3.6-plus") is None
