from pathlib import Path

import yaml

from server.config_registry import keys
from server.config_registry.registry import config_registry


def test_chat_replay_contract_defines_roles_kinds_and_invariants() -> None:
    candidates = config_registry.invariant_contract_paths(keys.CHAT_REPLAY_CONTRACT_NAME)
    path = candidates[0]
    assert path.exists()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["order_source"]["canonical"] == "chat_publish_order"
    assert payload["order_source"]["scope"] == "run"
    assert payload["roles"] == ["user", "assistant", "system"]
    assert "interaction_reply" in payload["kinds"]
    assert "assistant_process" in payload["kinds"]
    assert "assistant_message" in payload["kinds"]
    assert "assistant_final" in payload["kinds"]
    assert "no_local_render" in payload["invariants"]
    assert "assistant_final_prefers_display_text" in payload["invariants"]
    assert "live_history_consistent" in payload["invariants"]
