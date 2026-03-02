from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

STORE_FILES = [
    REPO_ROOT / "server/services/orchestration/run_store.py",
    REPO_ROOT / "server/services/skill/skill_install_store.py",
    REPO_ROOT / "server/services/skill/temp_skill_run_store.py",
    REPO_ROOT / "server/services/engine_management/engine_upgrade_store.py",
]


def _parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_import_targets(module: ast.Module) -> list[str]:
    targets: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            targets.append(node.module or "")
    return targets


def _store_classes(module: ast.Module) -> list[ast.ClassDef]:
    return [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Store")
    ]


def test_migrated_sqlite_stores_do_not_import_sqlite3() -> None:
    for path in STORE_FILES:
        module = _parse_module(path)
        imports = _iter_import_targets(module)
        assert "sqlite3" not in imports, f"{path} still imports sqlite3"


def test_migrated_sqlite_store_public_methods_are_async() -> None:
    for path in STORE_FILES:
        module = _parse_module(path)
        classes = _store_classes(module)
        assert classes, f"{path} should contain at least one *Store class"
        for class_node in classes:
            for method in class_node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if method.name == "__init__" or method.name.startswith("_"):
                    continue
                assert isinstance(
                    method, ast.AsyncFunctionDef
                ), f"{path}:{class_node.name}.{method.name} must be async def"
