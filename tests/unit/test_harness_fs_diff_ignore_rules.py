from pathlib import Path

from agent_harness.storage import snapshot_filesystem


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_harness_snapshot_ignores_internal_prefixes(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    _write(run_dir / "result" / "result.json", "{}")
    _write(run_dir / ".audit" / "meta.1.json", "{}")
    _write(run_dir / ".state" / "state.json", "{}")
    _write(run_dir / ".git" / "HEAD", "ref: refs/heads/main")
    _write(run_dir / ".claude" / "settings.json", "{}")
    _write(run_dir / ".codex" / "config.toml", "x")
    _write(run_dir / ".gemini" / "settings.json", "x")
    _write(run_dir / ".iflow" / "settings.json", "x")
    _write(run_dir / "opencode.json", "{}")

    rows = snapshot_filesystem(run_dir)
    paths = {row["path"] for row in rows}

    assert "result/result.json" in paths
    assert ".audit/meta.1.json" not in paths
    assert ".state/state.json" not in paths
    assert ".git/HEAD" not in paths
    assert ".claude/settings.json" not in paths
    assert ".codex/config.toml" not in paths
    assert ".gemini/settings.json" not in paths
    assert ".iflow/settings.json" not in paths
    assert "opencode.json" not in paths
