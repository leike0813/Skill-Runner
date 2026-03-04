from pathlib import Path

import yaml


def test_chat_replay_contract_defines_roles_kinds_and_invariants() -> None:
    path = Path("docs/contracts/chat_replay_contract.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["order_source"]["canonical"] == "chat_publish_order"
    assert payload["order_source"]["scope"] == "run"
    assert payload["roles"] == ["user", "assistant", "system"]
    assert "interaction_reply" in payload["kinds"]
    assert "assistant_final" in payload["kinds"]
    assert "no_local_render" in payload["invariants"]
    assert "live_history_consistent" in payload["invariants"]
