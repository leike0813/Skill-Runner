from __future__ import annotations

import ast
from pathlib import Path


def test_runtime_modules_do_not_import_orchestration() -> None:
    runtime_root = Path("server/runtime")
    violations: list[str] = []

    for path in runtime_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("server.services.orchestration"):
                    violations.append(f"{path}:{node.lineno}:{module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith("server.services.orchestration"):
                        violations.append(f"{path}:{node.lineno}:{name}")

    assert not violations, "runtime import boundary violations:\n" + "\n".join(violations)
