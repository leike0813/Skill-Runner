from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_dockerfile_uses_non_root_runtime_user() -> None:
    dockerfile = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")

    assert "useradd --system" in dockerfile
    assert "skillrunner" in dockerfile
    assert "USER skillrunner" in dockerfile
    assert "chown -R skillrunner:skillrunner /app /data /opt/cache /home/skillrunner" in dockerfile


def test_compose_documents_optional_data_bind_mount_permissions() -> None:
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "# Optional: persist run/request data for debugging" in compose
    assert "# If you enable ./data:/data, ensure ./data is writable by the container's non-root user." in compose
    assert "# Quick-and-dirty fallback: chmod 777 ./data" in compose
