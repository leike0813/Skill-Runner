from __future__ import annotations

import io
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_skill_runnerctl_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "skill_runnerctl.py"
    spec = importlib.util.spec_from_file_location("skill_runnerctl_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_returns_continue_result_for_partial_failure(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()

    profile = SimpleNamespace(mode="local", data_dir=tmp_path)
    monkeypatch.setattr(module, "_runtime_env", lambda: (profile, {"PATH": "fake"}))
    monkeypatch.setattr(
        module,
        "_runtime_dependency_checks",
        lambda: {"uv": True, "node": True, "npm": True},
    )

    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = io.StringIO("event=agent.ensure.summary phase=agent_ensure outcome=partial_failure\n")
            self.stderr = io.StringIO("")

        def wait(self) -> int:
            return self.returncode

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())  # noqa: ARG005

    exit_code = module.main(["bootstrap", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["ok"] is True
    assert payload["message"] == "Bootstrap completed."
    assert "partial_failure" in payload["stdout"]
    assert "partial_failure" in captured.err
    assert payload["bootstrap_report_file"].endswith("agent_bootstrap_report.json")
    assert "--bootstrap-report-file" in payload["command"]
