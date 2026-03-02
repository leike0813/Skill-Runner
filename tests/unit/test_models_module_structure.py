from pathlib import Path
import re

import server.models as models


def test_models_facade_is_thin_module() -> None:
    source_path = Path("server/models/__init__.py")
    source = source_path.read_text(encoding="utf-8")

    assert len(source.splitlines()) <= 220
    assert re.search(r"^class\\s+\\w+", source, flags=re.MULTILINE) is None


def test_models_package_owns_domain_modules() -> None:
    root = Path("server")
    package_root = root / "models"
    assert package_root.is_dir()
    assert (package_root / "__init__.py").is_file()
    assert not (root / "models.py").exists()
    assert not list(root.glob("models_*.py"))


def test_models_facade_exports_resolve() -> None:
    exported = getattr(models, "__all__", [])
    assert exported

    for name in exported:
        assert hasattr(models, name), f"missing export: {name}"
