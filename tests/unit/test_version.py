from pathlib import Path
import tomllib

from server.main import app
from server.version import get_backend_version


def test_get_backend_version_returns_current_project_version():
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    assert get_backend_version() == payload["project"]["version"]


def test_fastapi_metadata_uses_backend_version():
    assert app.version == get_backend_version()
