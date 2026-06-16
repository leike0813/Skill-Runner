import json
import zipfile
from pathlib import Path

from server.services.orchestration.job_orchestrator import JobOrchestrator


def test_bundle_manifest_includes_run_files(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / ".audit").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "result").mkdir(parents=True)
    (run_dir / "workspace" / "node_modules" / "pkg").mkdir(parents=True)

    (run_dir / ".audit" / "request_input.json").write_text('{"ok": true}')
    (run_dir / ".audit" / "stdout.1.log").write_text("stdout")
    (run_dir / "artifacts" / "text.md").write_text("artifact")
    (run_dir / "result" / "result.json").write_text('{"status":"success"}')
    (run_dir / "workspace" / "node_modules" / "pkg" / "index.js").write_text("ignored")

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(run_dir, debug=True)

    bundle_path = run_dir / bundle_rel
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        entries = set(zf.namelist())
        assert "bundle/manifest_debug.json" in entries
        assert "bundle/run_bundle_debug.zip" not in entries

        manifest = json.loads(zf.read("bundle/manifest_debug.json").decode("utf-8"))
        paths = {entry["path"] for entry in manifest["files"]}

    assert ".audit/request_input.json" in paths
    assert ".audit/stdout.1.log" in paths
    assert "artifacts/text.md" in paths
    assert "result/result.json" in paths
    assert "workspace/node_modules/pkg/index.js" not in paths


def test_bundle_manifest_debug_false_filters_logs(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / ".audit").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "result").mkdir(parents=True)

    (run_dir / ".audit" / "stdout.1.log").write_text("stdout")
    (run_dir / "artifacts" / "text.md").write_text("artifact")
    (run_dir / "result" / "result.json").write_text(
        '{"status":"success","artifacts":["artifacts/text.md"]}'
    )
    (run_dir / "uploads" / "input.txt").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "uploads" / "input.txt").write_text("upload")

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(run_dir, debug=False)

    bundle_path = run_dir / bundle_rel
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        entries = set(zf.namelist())
        assert "bundle/manifest.json" in entries
        assert ".audit/stdout.1.log" not in entries
        assert "artifacts/text.md" in entries
        assert "result/result.json" in entries
        assert "uploads/input.txt" not in entries


def test_bundle_manifest_includes_namespaced_feedback_sidecar(tmp_path):
    run_dir = tmp_path / "run"
    result_dir = run_dir / "result" / "demo-skill.1"
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        '{"status":"success","artifacts":[]}',
        encoding="utf-8",
    )
    (result_dir / "_skill_run_feedback.md").write_text("feedback", encoding="utf-8")

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(run_dir, debug=False)

    with zipfile.ZipFile(run_dir / bundle_rel, "r") as zf:
        entries = set(zf.namelist())
        payload = json.loads(zf.read("result/demo-skill.1/result.json").decode("utf-8"))

    assert "result/demo-skill.1/result.json" in entries
    assert "result/demo-skill.1/_skill_run_feedback.md" in entries
    assert "_skill_run_feedback.md" not in payload.get("artifacts", [])


def test_bundle_manifest_includes_legacy_feedback_sidecar(tmp_path):
    run_dir = tmp_path / "run"
    result_dir = run_dir / "result"
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        '{"status":"success","artifacts":[]}',
        encoding="utf-8",
    )
    (result_dir / "_skill_run_feedback.md").write_text("feedback", encoding="utf-8")

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(run_dir, debug=False)

    with zipfile.ZipFile(run_dir / bundle_rel, "r") as zf:
        entries = set(zf.namelist())

    assert "result/result.json" in entries
    assert "result/_skill_run_feedback.md" in entries


def test_build_run_bundle_public_api_writes_bundle(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "result").mkdir(parents=True)
    (run_dir / "artifacts" / "report.txt").write_text("artifact")
    (run_dir / "result" / "result.json").write_text(
        '{"status":"success","artifacts":["artifacts/report.txt"]}'
    )

    orchestrator = JobOrchestrator()
    public_rel = orchestrator.build_run_bundle(run_dir, debug=False)
    assert (run_dir / public_rel).exists()
