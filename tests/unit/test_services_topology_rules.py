from __future__ import annotations

from pathlib import Path


def test_services_root_has_no_flat_legacy_modules() -> None:
    services_root = Path(__file__).resolve().parents[2] / "server" / "services"
    legacy_py_files = sorted(
        path.name
        for path in services_root.glob("*.py")
        if path.name != "__init__.py"
    )
    assert legacy_py_files == [], (
        "Legacy flat service modules should be removed from server/services root: "
        + ", ".join(legacy_py_files)
    )

