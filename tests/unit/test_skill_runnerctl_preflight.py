from __future__ import annotations

import hashlib
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_text_lf(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_integrity_manifest(module, project_root: Path, file_entries: list[tuple[str, str]]) -> None:
    manifest_path = project_root / module.INTEGRITY_MANIFEST_NAME
    payload = {
        "schema_version": 1,
        "generated_at": "2026-03-13T00:00:00Z",
        "scope": {"directories": ["server", "scripts"], "files": ["pyproject.toml", "uv.lock", "docker-compose.yml"]},
        "files": [
            {"path": rel_path, "sha256": _sha256_text(content), "size": len(content.encode("utf-8"))}
            for rel_path, content in file_entries
        ],
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")


def _prepare_preflight_runtime(monkeypatch, module, tmp_path: Path) -> tuple[SimpleNamespace, Path, dict[str, Path]]:
    profile = SimpleNamespace(
        mode="local",
        data_dir=tmp_path / "data",
        agent_cache_root=tmp_path / "cache",
        agent_home=tmp_path / "agent-home",
    )
    profile.data_dir.mkdir(parents=True, exist_ok=True)
    profile.agent_cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "_runtime_env", lambda: (profile, {"SKILL_RUNNER_LOCAL_BIND_HOST": "127.0.0.1"}))

    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "_project_root", lambda: project_root)

    server_dir = project_root / "server"
    scripts_dir = project_root / "scripts"
    server_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    api_entry = server_dir / "main.py"
    agent_manager = scripts_dir / "agent_manager.py"
    api_content = "app = object()\n"
    manager_content = "print('ok')\n"
    _write_text_lf(api_entry, api_content)
    _write_text_lf(agent_manager, manager_content)
    monkeypatch.setattr(
        module,
        "_preflight_required_files",
        lambda: {"api_entry": api_entry, "agent_manager": agent_manager},
    )
    _write_integrity_manifest(
        module,
        project_root,
        [
            ("server/main.py", api_content),
            ("scripts/agent_manager.py", manager_content),
        ],
    )
    return profile, project_root, {"api_entry": api_entry, "agent_manager": agent_manager}


def test_preflight_passes_when_environment_ready(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert payload["blocking_issues"] == []
    assert payload["warnings"] == []
    assert payload["suggested_next"]["port"] == 29813


def test_preflight_claude_sandbox_dependency_warning_is_non_blocking(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    monkeypatch.setattr(
        module,
        "_claude_sandbox_status",
        lambda _profile: {
            "declared_enabled": True,
            "dependency_status": "warning",
            "dependencies": {"bubblewrap": False, "socat": False},
            "missing_dependencies": ["bubblewrap", "socat"],
            "warning_code": "CLAUDE_SANDBOX_DEPENDENCY_MISSING",
            "message": "Claude sandbox dependencies missing: bubblewrap, socat. Runs continue with warning-only observability.",
        },
    )
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert payload["checks"]["claude_sandbox"]["warning_code"] == "CLAUDE_SANDBOX_DEPENDENCY_MISSING"
    assert any(warning["code"] == "claude_sandbox_dependency_missing" for warning in payload["warnings"])


def test_preflight_missing_dependency_returns_exit_2(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": False, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert any(
        issue["code"] == "missing_dependency" and issue["component"] == "uv"
        for issue in payload["blocking_issues"]
    )


def test_preflight_port_unavailable_returns_exit_1(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (None, [29813, 29814]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json", "--port", "29813", "--port-fallback-span", "1"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert any(issue["code"] == "port_unavailable" for issue in payload["blocking_issues"])
    assert payload["checks"]["port"]["tried_ports"] == [29813, 29814]


def test_preflight_partial_failure_report_is_warning(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "partial_failure"}}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert any(warning["code"] == "bootstrap_partial_failure" for warning in payload["warnings"])


def test_preflight_stale_state_file_is_warning(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, _project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    monkeypatch.setattr(module, "_is_pid_alive", lambda _pid: False)
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    state_file = profile.agent_cache_root / "local_runtime_service.json"
    state_file.write_text(
        json.dumps({"pid": 424242, "host": "127.0.0.1", "port": 29813}),
        encoding="utf-8",
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert any(warning["code"] == "stale_state_file" for warning in payload["warnings"])


def test_preflight_missing_integrity_manifest_returns_exit_2(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, project_root, _required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )
    (project_root / module.INTEGRITY_MANIFEST_NAME).unlink()

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert any(issue["code"] == "integrity_manifest_missing" for issue in payload["blocking_issues"])


def test_preflight_integrity_missing_file_returns_exit_2(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, project_root, required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    required_files["agent_manager"].unlink()
    _write_integrity_manifest(
        module,
        project_root,
        [
            ("server/main.py", required_files["api_entry"].read_text(encoding="utf-8")),
            ("scripts/agent_manager.py", "print('ok')\n"),
        ],
    )

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert any(issue["code"] == "integrity_file_missing" for issue in payload["blocking_issues"])


def test_preflight_integrity_hash_mismatch_returns_exit_2(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()
    profile, project_root, required_files = _prepare_preflight_runtime(monkeypatch, module, tmp_path)
    monkeypatch.setattr(module, "_runtime_dependency_checks", lambda: {"uv": True, "node": True, "npm": True})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29813, [29813]))
    (profile.data_dir / "agent_bootstrap_report.json").write_text(
        json.dumps({"summary": {"outcome": "success"}}),
        encoding="utf-8",
    )

    _write_integrity_manifest(
        module,
        project_root,
        [
            ("server/main.py", required_files["api_entry"].read_text(encoding="utf-8")),
            ("scripts/agent_manager.py", "print('original')\n"),
        ],
    )
    _write_text_lf(required_files["agent_manager"], "print('changed')\n")

    exit_code = module.main(["preflight", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert any(issue["code"] == "integrity_hash_mismatch" for issue in payload["blocking_issues"])
