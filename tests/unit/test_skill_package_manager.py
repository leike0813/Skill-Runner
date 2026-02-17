import io
import json
import zipfile
from pathlib import Path

import pytest

from server.config import config
from server.services.skill_install_store import SkillInstallStore
from server.services.skill_package_manager import SkillPackageManager


def _build_skill_zip(
    skill_id: str,
    version: str,
    *,
    skill_name: str | None = None,
    runner_id: str | None = None,
    include_input_schema: bool = True,
    include_output_schema: bool = True,
    engines: list[str] | None = None,
    artifacts: list[dict] | None = None,
    extra_entries: dict[str, str | bytes] | None = None,
) -> bytes:
    if skill_name is None:
        skill_name = skill_id
    if runner_id is None:
        runner_id = skill_id
    if engines is None:
        engines = ["gemini"]
    if artifacts is None:
        artifacts = [{"role": "result", "pattern": "artifacts/out.json", "required": True}]

    runner = {
        "id": runner_id,
        "version": version,
        "engines": engines,
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": artifacts,
    }
    skill_md = (
        "---\n"
        f"name: {skill_name}\n"
        "description: test skill\n"
        "---\n\n"
        "# Test Skill\n"
    )

    input_schema = {"type": "object", "properties": {}}
    parameter_schema = {"type": "object", "properties": {}}
    output_schema = {
        "type": "object",
        "properties": {"result": {"type": "string", "x-type": "artifact"}},
        "required": ["result"],
    }

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", skill_md)
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        if include_input_schema:
            zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps(input_schema))
            zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps(parameter_schema))
        if include_output_schema:
            zf.writestr(f"{skill_id}/assets/output.schema.json", json.dumps(output_schema))
        for rel_path, content in (extra_entries or {}).items():
            zf.writestr(rel_path, content)
    return bio.getvalue()


@pytest.fixture
def isolated_skill_paths(tmp_path):
    old_skills_dir = config.SYSTEM.SKILLS_DIR
    old_archive_dir = config.SYSTEM.SKILLS_ARCHIVE_DIR
    old_staging_dir = config.SYSTEM.SKILLS_STAGING_DIR
    old_install_dir = config.SYSTEM.SKILL_INSTALLS_DIR
    old_install_db = config.SYSTEM.SKILL_INSTALLS_DB
    old_invalid_dir = config.SYSTEM.SKILLS_INVALID_DIR

    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(tmp_path / "skills")
    config.SYSTEM.SKILLS_ARCHIVE_DIR = str(tmp_path / "skills" / ".archive")
    config.SYSTEM.SKILLS_STAGING_DIR = str(tmp_path / "skills" / ".staging")
    config.SYSTEM.SKILLS_INVALID_DIR = str(tmp_path / "skills" / ".invalid")
    config.SYSTEM.SKILL_INSTALLS_DIR = str(tmp_path / "skill_installs")
    config.SYSTEM.SKILL_INSTALLS_DB = str(tmp_path / "skill_installs.db")
    config.freeze()
    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_skills_dir
        config.SYSTEM.SKILLS_ARCHIVE_DIR = old_archive_dir
        config.SYSTEM.SKILLS_STAGING_DIR = old_staging_dir
        config.SYSTEM.SKILLS_INVALID_DIR = old_invalid_dir
        config.SYSTEM.SKILL_INSTALLS_DIR = old_install_dir
        config.SYSTEM.SKILL_INSTALLS_DB = old_install_db
        config.freeze()


def test_install_new_skill(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)

    manager = SkillPackageManager()
    payload = _build_skill_zip("demo-upload", "1.0.0")
    manager.create_install_request("req-1", payload)
    manager.run_install("req-1")

    row = store.get_install("req-1")
    assert row is not None
    assert row["status"] == "succeeded"
    assert row["action"] == "install"
    assert (Path(config.SYSTEM.SKILLS_DIR) / "demo-upload" / "assets" / "runner.json").exists()


def test_install_strips_git_directory_and_preserves_non_git_hidden_entries(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)

    manager = SkillPackageManager()
    payload = _build_skill_zip(
        "demo-upload",
        "1.0.0",
        extra_entries={
            "demo-upload/.git/config": "[core]\n\trepositoryformatversion = 0\n",
            "demo-upload/.github/workflows/ci.yml": "name: ci\n",
            "demo-upload/.gitignore": "*.pyc\n",
        },
    )
    manager.create_install_request("req-1", payload)
    manager.run_install("req-1")

    row = store.get_install("req-1")
    assert row is not None
    assert row["status"] == "succeeded"
    live_dir = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload"
    assert not (live_dir / ".git").exists()
    assert (live_dir / ".github" / "workflows" / "ci.yml").exists()
    assert (live_dir / ".gitignore").exists()


def test_update_archives_old_version(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "1.0.0"))
    manager.run_install("req-1")
    manager.create_install_request("req-2", _build_skill_zip("demo-upload", "1.1.0"))
    manager.run_install("req-2")

    row = store.get_install("req-2")
    assert row is not None
    assert row["status"] == "succeeded"
    assert row["action"] == "update"

    archive_runner = Path(config.SYSTEM.SKILLS_ARCHIVE_DIR) / "demo-upload" / "1.0.0" / "assets" / "runner.json"
    assert archive_runner.exists()
    live_runner = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload" / "assets" / "runner.json"
    assert json.loads(live_runner.read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_update_strips_git_file_in_uploaded_package(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "1.0.0"))
    manager.run_install("req-1")
    manager.create_install_request(
        "req-2",
        _build_skill_zip(
            "demo-upload",
            "1.1.0",
            extra_entries={"demo-upload/.git": "gitdir: /tmp/external-repo\n"},
        ),
    )
    manager.run_install("req-2")

    row = store.get_install("req-2")
    assert row is not None
    assert row["status"] == "succeeded"
    live_dir = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload"
    assert not (live_dir / ".git").exists()
    live_runner = live_dir / "assets" / "runner.json"
    assert json.loads(live_runner.read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_reject_downgrade(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "2.0.0"))
    manager.run_install("req-1")
    manager.create_install_request("req-2", _build_skill_zip("demo-upload", "1.9.0"))
    manager.run_install("req-2")

    row = store.get_install("req-2")
    assert row is not None
    assert row["status"] == "failed"
    assert "strictly higher version" in (row["error"] or "")


def test_reject_missing_required_files(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    manager = SkillPackageManager()

    manager.create_install_request(
        "req-1",
        _build_skill_zip("demo-upload", "1.0.0", include_output_schema=False)
    )
    manager.run_install("req-1")

    row = store.get_install("req-1")
    assert row is not None
    assert row["status"] == "failed"
    assert "missing required files" in (row["error"] or "")


def test_reject_identity_mismatch(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    manager = SkillPackageManager()

    manager.create_install_request(
        "req-1",
        _build_skill_zip("demo-upload", "1.0.0", skill_name="wrong-name")
    )
    manager.run_install("req-1")

    row = store.get_install("req-1")
    assert row is not None
    assert row["status"] == "failed"
    assert "identity mismatch" in (row["error"] or "").lower()


def test_reject_existing_archive_path(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "1.0.0"))
    manager.run_install("req-1")
    archive_path = Path(config.SYSTEM.SKILLS_ARCHIVE_DIR) / "demo-upload" / "1.0.0"
    archive_path.mkdir(parents=True, exist_ok=True)

    manager.create_install_request("req-2", _build_skill_zip("demo-upload", "1.1.0"))
    manager.run_install("req-2")

    row = store.get_install("req-2")
    assert row is not None
    assert row["status"] == "failed"
    assert "archive already exists" in (row["error"] or "").lower()


def test_rolls_back_when_swap_fails(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "1.0.0"))
    manager.run_install("req-1")

    import server.services.skill_package_manager as mod
    real_move = mod.shutil.move
    state = {"first_done": False}

    def flaky_move(src, dst):
        src_path = Path(src)
        dst_path = Path(dst)
        if src_path.name == "demo-upload" and "archive" in dst_path.as_posix() and not state["first_done"]:
            state["first_done"] = True
            return real_move(src, dst)
        if src_path.name == "demo-upload" and dst_path.name == "demo-upload" and state["first_done"]:
            raise RuntimeError("swap failed")
        return real_move(src, dst)

    monkeypatch.setattr(mod.shutil, "move", flaky_move)
    manager.create_install_request("req-2", _build_skill_zip("demo-upload", "1.1.0"))
    manager.run_install("req-2")

    row = store.get_install("req-2")
    assert row is not None
    assert row["status"] == "failed"
    live_runner = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload" / "assets" / "runner.json"
    assert json.loads(live_runner.read_text(encoding="utf-8"))["version"] == "1.0.0"


def test_invalid_existing_directory_is_quarantined_and_reinstalled(monkeypatch, isolated_skill_paths):
    store = SkillInstallStore(db_path=Path(config.SYSTEM.SKILL_INSTALLS_DB))
    monkeypatch.setattr("server.services.skill_package_manager.skill_install_store", store)
    monkeypatch.setattr("server.services.skill_package_manager.skill_registry.scan_skills", lambda: None)
    manager = SkillPackageManager()

    broken_dir = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "SKILL.md").write_text("# Broken skill", encoding="utf-8")

    manager.create_install_request("req-1", _build_skill_zip("demo-upload", "1.0.0"))
    manager.run_install("req-1")

    row = store.get_install("req-1")
    assert row is not None
    assert row["status"] == "succeeded"
    assert row["action"] == "install"

    invalid_root = Path(config.SYSTEM.SKILLS_INVALID_DIR)
    quarantined = list(invalid_root.glob("demo-upload-*"))
    assert quarantined, "expected invalid existing directory to be quarantined"

    live_runner = Path(config.SYSTEM.SKILLS_DIR) / "demo-upload" / "assets" / "runner.json"
    assert live_runner.exists()
    assert json.loads(live_runner.read_text(encoding="utf-8"))["version"] == "1.0.0"
