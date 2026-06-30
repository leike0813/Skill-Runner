from server.main import app
from server.version import get_backend_version


def test_get_backend_version_returns_current_project_version():
    assert get_backend_version() == "0.7.2"


def test_fastapi_metadata_uses_backend_version():
    assert app.version == get_backend_version()
