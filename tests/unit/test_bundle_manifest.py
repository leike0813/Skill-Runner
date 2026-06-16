import json
import zipfile
from pathlib import Path

from server.runtime.workspace_layout import RunWorkspaceLayout
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


def test_build_run_bundle_with_layout_isolates_namespaced_results(tmp_path):
    workspace = tmp_path / "workspace"
    artifact_a = workspace / "artifacts" / "a.txt"
    artifact_b = workspace / "artifacts" / "b.txt"
    result_a = workspace / "result" / "skill-a.1"
    result_b = workspace / "result" / "skill-b.1"
    result_a.mkdir(parents=True)
    result_b.mkdir(parents=True)
    artifact_a.parent.mkdir(parents=True)
    artifact_a.write_text("artifact-a", encoding="utf-8")
    artifact_b.write_text("artifact-b", encoding="utf-8")
    (result_a / "result.json").write_text(
        '{"status":"success","artifacts":["artifacts/a.txt"]}',
        encoding="utf-8",
    )
    (result_a / "_skill_run_feedback.md").write_text("feedback-a", encoding="utf-8")
    (result_b / "result.json").write_text(
        '{"status":"success","artifacts":["artifacts/b.txt"]}',
        encoding="utf-8",
    )
    (result_b / "_skill_run_feedback.md").write_text("feedback-b", encoding="utf-8")

    layout_a = RunWorkspaceLayout(
        workspace_id="workspace",
        workspace_dir=workspace,
        namespace="skill-a.1",
    )
    layout_b = RunWorkspaceLayout(
        workspace_id="workspace",
        workspace_dir=workspace,
        namespace="skill-b.1",
    )

    orchestrator = JobOrchestrator()
    bundle_a_rel = orchestrator.build_run_bundle(workspace, debug=False, layout=layout_a)
    bundle_b_rel = orchestrator.build_run_bundle(workspace, debug=False, layout=layout_b)

    assert bundle_a_rel == "bundle/skill-a.1/run_bundle.zip"
    assert bundle_b_rel == "bundle/skill-b.1/run_bundle.zip"
    assert (workspace / bundle_a_rel).exists()
    assert (workspace / bundle_b_rel).exists()

    with zipfile.ZipFile(workspace / bundle_a_rel, "r") as zf:
        entries_a = set(zf.namelist())
    with zipfile.ZipFile(workspace / bundle_b_rel, "r") as zf:
        entries_b = set(zf.namelist())

    assert "bundle/skill-a.1/manifest.json" in entries_a
    assert "result/skill-a.1/result.json" in entries_a
    assert "result/skill-a.1/_skill_run_feedback.md" in entries_a
    assert "artifacts/a.txt" in entries_a
    assert "result/skill-b.1/result.json" not in entries_a
    assert "artifacts/b.txt" not in entries_a

    assert "bundle/skill-b.1/manifest.json" in entries_b
    assert "result/skill-b.1/result.json" in entries_b
    assert "result/skill-b.1/_skill_run_feedback.md" in entries_b
    assert "artifacts/b.txt" in entries_b
    assert "result/skill-a.1/result.json" not in entries_b
    assert "artifacts/a.txt" not in entries_b


def test_debug_bundle_with_layout_isolates_namespaced_run_owned_files(tmp_path):
    workspace = tmp_path / "workspace"
    for namespace in ("skill-a.1", "skill-b.1"):
        (workspace / "result" / namespace).mkdir(parents=True)
        (workspace / ".audit" / namespace).mkdir(parents=True)
        (workspace / ".state" / namespace).mkdir(parents=True)
        (workspace / "result" / namespace / "result.json").write_text(
            '{"status":"success","artifacts":[]}',
            encoding="utf-8",
        )
        (workspace / ".audit" / namespace / "stdout.1.log").write_text(
            f"stdout-{namespace}",
            encoding="utf-8",
        )
        (workspace / ".state" / namespace / "state.json").write_text(
            '{"status":"succeeded"}',
            encoding="utf-8",
        )

    layout_a = RunWorkspaceLayout(
        workspace_id="workspace",
        workspace_dir=workspace,
        namespace="skill-a.1",
    )

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(workspace, debug=True, layout=layout_a)

    assert bundle_rel == "bundle/skill-a.1/run_bundle_debug.zip"
    with zipfile.ZipFile(workspace / bundle_rel, "r") as zf:
        entries = set(zf.namelist())

    assert "bundle/skill-a.1/manifest_debug.json" in entries
    assert "result/skill-a.1/result.json" in entries
    assert ".audit/skill-a.1/stdout.1.log" in entries
    assert ".state/skill-a.1/state.json" in entries
    assert "result/skill-b.1/result.json" not in entries
    assert ".audit/skill-b.1/stdout.1.log" not in entries
    assert ".state/skill-b.1/state.json" not in entries


def test_build_run_bundle_with_layout_missing_result_does_not_fallback_to_other_namespaces(tmp_path):
    workspace = tmp_path / "workspace"
    other_result = workspace / "result" / "skill-b.1"
    other_result.mkdir(parents=True)
    (other_result / "result.json").write_text(
        '{"status":"success","artifacts":[]}',
        encoding="utf-8",
    )
    layout_a = RunWorkspaceLayout(
        workspace_id="workspace",
        workspace_dir=workspace,
        namespace="skill-a.1",
    )

    orchestrator = JobOrchestrator()
    bundle_rel = orchestrator.build_run_bundle(workspace, debug=False, layout=layout_a)

    with zipfile.ZipFile(workspace / bundle_rel, "r") as zf:
        entries = set(zf.namelist())

    assert "bundle/skill-a.1/manifest.json" in entries
    assert "result/skill-b.1/result.json" not in entries
