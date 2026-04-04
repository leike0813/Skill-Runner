from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from server.services.engine_management.auth_import_service import (
    AuthImportError,
    AuthImportService,
)
from server.services.engine_management.auth_import_validator_registry import (
    AuthImportValidationError,
)


def _build_service(tmp_path: Path) -> AuthImportService:
    service = AuthImportService()
    service._runtime_profile = SimpleNamespace(agent_home=tmp_path / "agent-home")
    return service


def test_get_import_spec_gemini_uses_profile_required_files(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    spec = service.get_import_spec(engine="gemini")

    assert spec["engine"] == "gemini"
    assert spec["supported"] is True
    ask_user = spec["ask_user"]
    assert ask_user["kind"] == "upload_files"
    assert [item["name"] for item in ask_user["files"] if item["required"] is True] == [
        "google_accounts.json",
        "oauth_creds.json",
    ]
    assert "required_files" not in spec
    assert "optional_files" not in spec


def test_import_auth_files_opencode_openai_accepts_codex_auth_json(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    codex_payload = {
        "tokens": {
            "refresh_token": "refresh-token",
            "access_token": "access-token",
            "account_id": "acct-1",
        }
    }

    result = service.import_auth_files(
        engine="opencode",
        provider_id="openai",
        files={"auth.json": json.dumps(codex_payload).encode("utf-8")},
    )

    target = tmp_path / "agent-home" / ".local" / "share" / "opencode" / "auth.json"
    assert target.exists()
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["openai"]["type"] == "oauth"
    assert parsed["openai"]["refresh"] == "refresh-token"
    assert parsed["openai"]["access"] == "access-token"
    assert result["risk_notice_required"] is False


def test_import_auth_files_gemini_requires_all_required_files(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    with pytest.raises(AuthImportError, match="Missing required files"):
        service.import_auth_files(
            engine="gemini",
            files={"oauth_creds.json": b'{"refresh_token":"x"}'},
        )


def test_import_auth_files_opencode_google_requires_google_entry(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    payload = {
        "openai": {
            "type": "oauth",
            "refresh": "r",
            "access": "a",
        }
    }

    with pytest.raises(AuthImportValidationError, match="provider `google`"):
        service.import_auth_files(
            engine="opencode",
            provider_id="google",
            files={"auth.json": json.dumps(payload).encode("utf-8")},
        )


def test_import_auth_files_opencode_replaces_only_selected_provider(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    existing_path = tmp_path / "agent-home" / ".local" / "share" / "opencode" / "auth.json"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(
        json.dumps(
            {
                "google": {
                    "type": "oauth",
                    "refresh": "google-refresh",
                    "access": "google-access",
                },
                "openai": {
                    "type": "oauth",
                    "refresh": "old-openai-refresh",
                    "access": "old-openai-access",
                },
            }
        ),
        encoding="utf-8",
    )
    incoming_payload = {
        "openai": {
            "type": "oauth",
            "refresh": "new-openai-refresh",
            "access": "new-openai-access",
        }
    }

    service.import_auth_files(
        engine="opencode",
        provider_id="openai",
        files={"auth.json": json.dumps(incoming_payload).encode("utf-8")},
    )

    parsed = json.loads(existing_path.read_text(encoding="utf-8"))
    assert parsed["google"]["refresh"] == "google-refresh"
    assert parsed["openai"]["refresh"] == "new-openai-refresh"


def test_get_import_spec_claude_uses_credentials_json(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    spec = service.get_import_spec(engine="claude")

    assert spec["engine"] == "claude"
    assert spec["supported"] is True
    ask_user = spec["ask_user"]
    assert ask_user["kind"] == "upload_files"
    assert [item["name"] for item in ask_user["files"] if item["required"] is True] == [
        ".credentials.json",
    ]


def test_get_import_spec_qwen_oauth_uses_oauth_creds_json(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    spec = service.get_import_spec(engine="qwen", provider_id="qwen-oauth")

    assert spec["engine"] == "qwen"
    assert spec["provider_id"] == "qwen-oauth"
    assert spec["supported"] is True
    assert [item["name"] for item in spec["ask_user"]["files"]] == ["oauth_creds.json"]


def test_get_import_spec_qwen_coding_plan_rejects_import(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    with pytest.raises(AuthImportError, match="does not support import auth"):
        service.get_import_spec(engine="qwen", provider_id="coding-plan-china")


def test_import_auth_files_qwen_oauth_writes_oauth_creds(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    result = service.import_auth_files(
        engine="qwen",
        provider_id="qwen-oauth",
        files={"oauth_creds.json": b'{"refresh_token":"x"}'},
    )

    target = tmp_path / "agent-home" / ".qwen" / "oauth_creds.json"
    assert target.exists()
    assert result["provider_id"] == "qwen-oauth"
