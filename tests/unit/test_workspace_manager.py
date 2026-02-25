import json
import pytest
from pathlib import Path
from server.services.workspace_manager import workspace_manager
from server.models import RunCreateRequest, SkillManifest


@pytest.fixture(autouse=True)
def _allow_test_skill(monkeypatch, tmp_path):
    skill = SkillManifest(
        id="test-skill",
        name="test-skill",
        engines=["codex", "gemini", "iflow", "opencode"],
        path=tmp_path
    )

    monkeypatch.setattr(
        "server.services.skill_registry.skill_registry.get_skill",
        lambda skill_id: skill if skill_id == "test-skill" else None
    )

def test_create_run_structure(tmp_path):
    # Mock config RUNS_DIR 
    # (In integration we depend on real config, here we might want to patch it, 
    # but WorkspaceManager imports config globally. 
    # For simplicity, we assume we use the global config or patch it)
    
    # Actually, workspace_manager uses `config.RUNS_DIR`.
    # Let's patch `server.config.config.RUNS_DIR`
    
    from server.config import config
    
    # Save old
    old_runs_dir = config.SYSTEM.RUNS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.freeze()
    
    try:
        req = RunCreateRequest(skill_id="test-skill", parameter={"p": 1})
        resp = workspace_manager.create_run(req)
        
        assert resp.run_id is not None
        assert resp.status == "queued"
        
        run_dir = Path(config.SYSTEM.RUNS_DIR) / resp.run_id
        assert run_dir.exists()
        assert (run_dir / "input.json").exists()
        assert (run_dir / "artifacts").exists()
        assert (run_dir / "result").exists()
        assert (run_dir / "interactions").exists()
        assert (run_dir / "uploads").exists() == False
        
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.freeze()


def test_create_run_rejects_unsupported_engine(tmp_path, monkeypatch):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.freeze()

    skill = SkillManifest(
        id="test-skill",
        name="test-skill",
        engines=["codex"],
        path=tmp_path
    )
    monkeypatch.setattr(
        "server.services.skill_registry.skill_registry.get_skill",
        lambda skill_id: skill if skill_id == "test-skill" else None
    )

    try:
        req = RunCreateRequest(skill_id="test-skill", engine="gemini", parameter={})
        with pytest.raises(ValueError, match="does not support engine"):
            workspace_manager.create_run(req)
        assert not Path(config.SYSTEM.RUNS_DIR).exists()
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.freeze()

def test_handle_upload(tmp_path):
    from server.config import config
    import io
    import zipfile
    
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()
    
    try:
        request_id = "req-1"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})
        
        # Create a dummy zip
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("test.txt", "content")
            
        workspace_manager.handle_upload(request_id, b.getvalue())
        
        request_dir = Path(config.SYSTEM.REQUESTS_DIR) / request_id
        assert (request_dir / "uploads" / "test.txt").exists()
        assert (request_dir / "uploads" / "test.txt").read_text() == "content"
        
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()

def test_handle_upload_nested_paths(tmp_path):
    from server.config import config
    import io
    import zipfile

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()

    try:
        request_id = "req-2"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})

        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("nested/inner.txt", "content")

        result = workspace_manager.handle_upload(request_id, b.getvalue())

        request_dir = Path(config.SYSTEM.REQUESTS_DIR) / request_id
        assert (request_dir / "uploads" / "nested" / "inner.txt").exists()
        assert "nested/inner.txt" in result["extracted_files"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()

def test_handle_upload_bad_zip(tmp_path):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()

    try:
        request_id = "req-3"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})

        with pytest.raises(ValueError, match="Invalid zip file"):
            workspace_manager.handle_upload(request_id, b"not-a-zip")
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()


def test_write_input_manifest_empty_uploads(tmp_path):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()

    try:
        request_id = "req-4"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})
        manifest_path = workspace_manager.write_input_manifest(request_id)
        assert manifest_path.exists()
        assert json.loads(manifest_path.read_text()) == {"files": []}
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()


def test_promote_request_uploads_moves_files(tmp_path):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()

    try:
        request_id = "req-5"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})
        request_uploads = Path(config.SYSTEM.REQUESTS_DIR) / request_id / "uploads"
        (request_uploads / "input.txt").write_text("content")

        run_response = workspace_manager.create_run(RunCreateRequest(skill_id="test-skill", parameter={}))
        workspace_manager.promote_request_uploads(request_id, run_response.run_id)

        run_uploads = Path(config.SYSTEM.RUNS_DIR) / run_response.run_id / "uploads"
        assert (run_uploads / "input.txt").exists()
        assert not request_uploads.exists()
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()


def test_promote_request_uploads_existing_target_raises(tmp_path):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.freeze()

    try:
        request_id = "req-6"
        workspace_manager.create_request(request_id, {"skill_id": "test-skill"})

        run_response = workspace_manager.create_run(RunCreateRequest(skill_id="test-skill", parameter={}))
        run_uploads = Path(config.SYSTEM.RUNS_DIR) / run_response.run_id / "uploads"
        run_uploads.mkdir()

        with pytest.raises(ValueError, match="Run uploads already exist"):
            workspace_manager.promote_request_uploads(request_id, run_response.run_id)
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.freeze()
