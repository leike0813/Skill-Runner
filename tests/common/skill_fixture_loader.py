import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List


def fixtures_skill_root(project_root: Path) -> Path:
    return project_root / "tests" / "fixtures" / "skills"


def fixture_skill_dir(project_root: Path, skill_fixture: str) -> Path:
    path = fixtures_skill_root(project_root) / skill_fixture
    if not path.exists() or not path.is_dir():
        raise RuntimeError(f"Fixture skill not found: {path}")
    return path


def load_fixture_runner(project_root: Path, skill_fixture: str) -> Dict[str, Any]:
    skill_dir = fixture_skill_dir(project_root, skill_fixture)
    runner_path = skill_dir / "assets" / "runner.json"
    if not runner_path.exists():
        raise RuntimeError(f"Fixture runner not found: {runner_path}")
    return json.loads(runner_path.read_text(encoding="utf-8"))


def fixture_skill_engines(project_root: Path, skill_fixture: str) -> List[str]:
    runner = load_fixture_runner(project_root, skill_fixture)
    engines = runner.get("engines")
    if engines is None:
        engines = runner.get("engine")
    if engines is None:
        return []
    if isinstance(engines, str):
        return [engines]
    return [str(item) for item in engines]


def fixture_skill_needs_input(project_root: Path, skill_fixture: str) -> bool:
    skill_dir = fixture_skill_dir(project_root, skill_fixture)
    return (skill_dir / "assets" / "input.schema.json").exists()


def build_fixture_skill_zip(project_root: Path, skill_fixture: str) -> bytes:
    skill_dir = fixture_skill_dir(project_root, skill_fixture)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in skill_dir.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(skill_dir).as_posix()
                zf.writestr(f"{skill_fixture}/{rel_path}", path.read_bytes())
    buffer.seek(0)
    return buffer.read()
