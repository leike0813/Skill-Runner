from __future__ import annotations

import base64
import json
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.engines.codebuddy.auth.credential_store import CodeBuddyCredentialStore
from server.engines.codebuddy.auth.provider_registry import (
    CODEBUDDY_PROVIDER_IDS,
    require_provider,
)


def _jwt_with_exp(expires_at: datetime) -> str:
    payload = json.dumps({"exp": int(expires_at.timestamp())}).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


def _store(tmp_path: Path) -> CodeBuddyCredentialStore:
    return CodeBuddyCredentialStore(
        path=tmp_path / "data" / "engine_credentials" / "codebuddy.json",
        agent_home=tmp_path / "agent-home",
    )


def test_provider_registry_is_canonical() -> None:
    assert CODEBUDDY_PROVIDER_IDS == ("codebuddy-cn", "codebuddy-global")
    assert require_provider("codebuddy-cn").runtime_environment == "internal"
    assert require_provider("codebuddy-global").runtime_environment == "public"
    with pytest.raises(ValueError):
        require_provider("internal")


def test_vault_keeps_providers_isolated_and_projects_no_token(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put("codebuddy-cn", token="domestic-secret", user_id="cn-user")
    store.put("codebuddy-global", token="global-secret", user_id="global-user")

    assert store.get("codebuddy-cn").token == "domestic-secret"  # type: ignore[union-attr]
    assert store.get("codebuddy-global").token == "global-secret"  # type: ignore[union-attr]
    assert store.project_status("codebuddy-cn").credential_state == "present"
    assert "token" not in store.project_status("codebuddy-cn").__dict__

    assert store.delete("codebuddy-cn") is True
    assert store.get("codebuddy-cn") is None
    assert store.get("codebuddy-global").token == "global-secret"  # type: ignore[union-attr]


def test_vault_uses_owner_only_permissions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put("codebuddy-cn", token="secret", user_id="user")

    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    assert payload["version"] == 1


def test_jwt_expiry_is_only_a_status_projection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    store.put("codebuddy-cn", token=_jwt_with_exp(expired), user_id="user")

    assert store.get("codebuddy-cn") is not None
    assert store.project_status("codebuddy-cn").credential_state == "expired"


def test_account_replacement_rotates_only_selected_provider_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cn_dir = require_provider("codebuddy-cn").config_dir(store.agent_home)
    global_dir = require_provider("codebuddy-global").config_dir(store.agent_home)
    cn_dir.mkdir(parents=True)
    global_dir.mkdir(parents=True)
    (cn_dir / "session.json").write_text("old", encoding="utf-8")
    (global_dir / "session.json").write_text("keep", encoding="utf-8")

    store.put("codebuddy-cn", token="old", user_id="old-user")
    assert cn_dir.exists()
    store.put("codebuddy-cn", token="new", user_id="new-user")

    assert not cn_dir.exists()
    assert (global_dir / "session.json").read_text(encoding="utf-8") == "keep"


def test_vault_rejects_symlink_file(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.path.parent.mkdir(parents=True)
    target = tmp_path / "external.json"
    target.write_text('{"version": 1, "providers": {}}', encoding="utf-8")
    store.path.symlink_to(target)

    with pytest.raises(ValueError):
        store.get("codebuddy-cn")
