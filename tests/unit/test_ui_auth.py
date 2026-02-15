import pytest
import base64

from server.services import ui_auth


def test_validate_ui_basic_auth_config_disabled(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    ui_auth.validate_ui_basic_auth_config()


def test_validate_ui_basic_auth_config_enabled_requires_credentials(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: True)
    monkeypatch.setattr("server.services.ui_auth.get_ui_basic_auth_credentials", lambda: ("", ""))
    with pytest.raises(RuntimeError, match="UI basic auth is enabled"):
        ui_auth.validate_ui_basic_auth_config()


def test_validate_ui_basic_auth_config_enabled_accepts_credentials(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: True)
    monkeypatch.setattr(
        "server.services.ui_auth.get_ui_basic_auth_credentials",
        lambda: ("admin", "secret"),
    )
    ui_auth.validate_ui_basic_auth_config()


def test_verify_ui_basic_auth_header(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: True)
    monkeypatch.setattr(
        "server.services.ui_auth.get_ui_basic_auth_credentials",
        lambda: ("admin", "secret"),
    )
    token = base64.b64encode(b"admin:secret").decode("ascii")
    assert ui_auth.verify_ui_basic_auth_header(f"Basic {token}") is True
    assert ui_auth.verify_ui_basic_auth_header("Basic bad-token") is False
    assert ui_auth.verify_ui_basic_auth_header(None) is False
