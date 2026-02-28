from pathlib import Path


def test_runtime_auth_has_no_engine_imports():
    runtime_root = Path(__file__).resolve().parents[2] / "server" / "runtime" / "auth"
    violations: list[str] = []
    for path in runtime_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "server.engines" in content:
            violations.append(f"{path}: contains server.engines import")
        if "from ..engines" in content or "from ...engines" in content:
            violations.append(f"{path}: contains relative engines import")
        if "import server.engines" in content:
            violations.append(f"{path}: contains absolute engines import")
    assert violations == []

