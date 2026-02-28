from pathlib import Path

from server.services.orchestration.job_orchestrator import JobOrchestrator


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_job_orchestrator_snapshot_ignores_internal_prefixes(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    _write(run_dir / "result" / "result.json", "{}")
    _write(run_dir / ".audit" / "meta.1.json", "{}")
    _write(run_dir / "interactions" / "pending.json", "{}")
    _write(run_dir / ".codex" / "config.toml", "x")
    _write(run_dir / ".gemini" / "settings.json", "x")
    _write(run_dir / ".iflow" / "settings.json", "x")
    _write(run_dir / "opencode.json", "{}")

    orchestrator = JobOrchestrator()
    snapshot = orchestrator._capture_filesystem_snapshot(run_dir)

    assert "result/result.json" in snapshot
    assert ".audit/meta.1.json" not in snapshot
    assert "interactions/pending.json" not in snapshot
    assert ".codex/config.toml" not in snapshot
    assert ".gemini/settings.json" not in snapshot
    assert ".iflow/settings.json" not in snapshot
    assert "opencode.json" not in snapshot
