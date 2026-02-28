from __future__ import annotations

import ast
from pathlib import Path


ALLOWED_SERVICE_DOMAINS = {"orchestration", "platform", "skill", "ui"}


def _collect_runtime_files() -> list[Path]:
    runtime_root = Path(__file__).resolve().parents[2] / "server" / "runtime"
    return sorted(path for path in runtime_root.rglob("*.py") if path.name != "__init__.py")


def test_runtime_modules_do_not_import_legacy_flat_services() -> None:
    violations: list[str] = []
    for file_path in _collect_runtime_files():
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        rel = file_path.relative_to(file_path.parents[3]).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("server.services."):
                    domain = module.split(".", 3)[2]
                    if domain not in ALLOWED_SERVICE_DOMAINS:
                        violations.append(f"{rel}: from {module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith("server.services."):
                        domain = name.split(".", 3)[2]
                        if domain not in ALLOWED_SERVICE_DOMAINS:
                            violations.append(f"{rel}: import {name}")
    assert violations == [], "Runtime imported legacy flat services:\n" + "\n".join(violations)

