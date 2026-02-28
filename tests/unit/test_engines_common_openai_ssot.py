from __future__ import annotations

import ast
from pathlib import Path


def test_engines_common_openai_auth_has_no_services_dependency() -> None:
    openai_auth_root = (
        Path(__file__).resolve().parents[2]
        / "server"
        / "engines"
        / "common"
        / "openai_auth"
    )
    violations: list[str] = []
    for file_path in sorted(openai_auth_root.rglob("*.py")):
        if file_path.name == "__init__.py":
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        rel = file_path.relative_to(file_path.parents[4]).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("server.services"):
                    violations.append(f"{rel}: from {module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("server.services"):
                        violations.append(f"{rel}: import {alias.name}")
    assert violations == [], "OpenAI common auth modules must not depend on server.services:\n" + "\n".join(
        violations
    )

