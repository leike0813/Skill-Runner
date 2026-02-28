import json
import zipfile
from pathlib import Path

from server.services.orchestration.job_orchestrator import JobOrchestrator


def test_bundle_manifest_includes_run_files(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "result").mkdir(parents=True)

    (run_dir / "input.json").write_text('{"ok": true}')
    (run_dir / "logs" / "stdout.txt").write_text("stdout")
    (run_dir / "artifacts" / "text.md").write_text("artifact")
    (run_dir / "result" / "result.json").write_text('{"status":"success"}')

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator._build_run_bundle(run_dir, debug=True)

    bundle_path = run_dir / bundle_rel
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        entries = set(zf.namelist())
        assert "bundle/manifest_debug.json" in entries
        assert "bundle/run_bundle_debug.zip" not in entries

        manifest = json.loads(zf.read("bundle/manifest_debug.json").decode("utf-8"))
        paths = {entry["path"] for entry in manifest["files"]}

    assert "input.json" in paths
    assert "logs/stdout.txt" in paths
    assert "artifacts/text.md" in paths
    assert "result/result.json" in paths


def test_bundle_manifest_debug_false_filters_logs(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "result").mkdir(parents=True)

    (run_dir / "logs" / "stdout.txt").write_text("stdout")
    (run_dir / "artifacts" / "text.md").write_text("artifact")
    (run_dir / "result" / "result.json").write_text('{"status":"success"}')

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator._build_run_bundle(run_dir, debug=False)

    bundle_path = run_dir / bundle_rel
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        entries = set(zf.namelist())
        assert "bundle/manifest.json" in entries
        assert "logs/stdout.txt" not in entries
        assert "artifacts/text.md" in entries
        assert "result/result.json" in entries
