import json
from pathlib import Path

from server.engines.opencode.auth.store import OpencodeAuthStore


def test_opencode_auth_store_upsert_api_key(tmp_path: Path):
    store = OpencodeAuthStore(tmp_path / "agent_home")
    store.upsert_api_key("deepseek", "sk-1")
    store.upsert_api_key("openrouter", "sk-2")

    payload = json.loads(store.auth_path.read_text(encoding="utf-8"))
    assert payload["deepseek"]["type"] == "api"
    assert payload["deepseek"]["key"] == "sk-1"
    assert payload["openrouter"]["key"] == "sk-2"


def test_opencode_auth_store_clear_antigravity_accounts(tmp_path: Path):
    store = OpencodeAuthStore(tmp_path / "agent_home")
    path = store.antigravity_accounts_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "accounts": [{"id": 1}, {"id": 2}],
                "active": "foo",
                "activeIndex": 1,
            }
        ),
        encoding="utf-8",
    )

    audit = store.clear_antigravity_accounts()
    assert audit["removed_accounts"] == 2

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["accounts"] == []
    assert payload["active"] is None
    assert payload["activeIndex"] == -1


def test_opencode_auth_store_backup_and_restore(tmp_path: Path):
    store = OpencodeAuthStore(tmp_path / "agent_home")
    source = store.antigravity_accounts_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({"accounts": [{"id": "a"}], "active": "a"}), encoding="utf-8")

    backup = store.backup_antigravity_accounts(tmp_path / "backup.json")
    assert backup["source_exists"] is True
    assert backup["backup_created"] is True
    assert backup["backup_path"]

    store.clear_antigravity_accounts()
    cleared = json.loads(source.read_text(encoding="utf-8"))
    assert cleared["accounts"] == []

    store.restore_antigravity_accounts(
        source_exists=True,
        backup_path=str(backup["backup_path"]),
    )
    restored = json.loads(source.read_text(encoding="utf-8"))
    assert restored["accounts"] == [{"id": "a"}]
