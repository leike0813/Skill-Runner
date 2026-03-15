from __future__ import annotations

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


def test_parser_defaults_use_service_port_9813(monkeypatch) -> None:
    monkeypatch.delenv("SKILL_RUNNER_LOCAL_PORT", raising=False)
    monkeypatch.delenv("SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    module = _load_skill_runnerctl_module()

    parser = module._build_parser()
    up_args = parser.parse_args(["up"])
    status_args = parser.parse_args(["status"])

    assert up_args.port == 9813
    assert up_args.port_fallback_span == 0
    assert status_args.port == 9813


def test_parser_defaults_use_plugin_port_and_fallback_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SKILL_RUNNER_LOCAL_PORT", "29813")
    monkeypatch.setenv("SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN", "10")
    module = _load_skill_runnerctl_module()

    parser = module._build_parser()
    up_args = parser.parse_args(["up"])
    status_args = parser.parse_args(["status"])

    assert up_args.port == 29813
    assert up_args.port_fallback_span == 10
    assert status_args.port == 29813


def test_collect_local_status_uses_lightweight_probe(monkeypatch, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()

    profile = SimpleNamespace(mode="local", data_dir=tmp_path / "data", agent_cache_root=tmp_path / "cache")
    monkeypatch.setattr(module, "_runtime_env", lambda: (profile, {"SKILL_RUNNER_LOCAL_BIND_HOST": "127.0.0.1"}))
    monkeypatch.setattr(module, "_state_file", lambda _profile: tmp_path / "state.json")
    monkeypatch.setattr(module, "_load_state", lambda _path: {"host": "127.0.0.1", "port": 9813, "pid": 4321})
    monkeypatch.setattr(module, "_is_pid_alive", lambda _pid: True)

    called_urls: list[str] = []

    def _fake_http_json(_method: str, url: str, **_kwargs):
        called_urls.append(url)
        return 204, {}

    monkeypatch.setattr(module, "_http_json", _fake_http_json)

    payload = module._collect_local_status(SimpleNamespace(port=9813))

    assert payload["service_healthy"] is True
    assert payload["status"] == "running"
    assert called_urls
    assert called_urls[0].endswith(module.HEALTH_PROBE_PATH)


def test_cmd_up_local_uses_fallback_port_when_requested_port_unavailable(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    module = _load_skill_runnerctl_module()

    profile = SimpleNamespace(mode="local", data_dir=tmp_path / "data", agent_cache_root=tmp_path / "cache")
    monkeypatch.setattr(module, "_runtime_env", lambda: (profile, {"SKILL_RUNNER_LOCAL_BIND_HOST": "127.0.0.1"}))
    monkeypatch.setattr(module, "_command_exists", lambda _: True)
    monkeypatch.setattr(module, "_collect_local_status", lambda _args: {"service_healthy": False})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (29814, [29813, 29814]))
    monkeypatch.setattr(module, "_start_local_process", lambda *_args: (4321, tmp_path / "local.log"))
    monkeypatch.setattr(module, "_http_json", lambda *_args, **_kwargs: (204, {}))
    monkeypatch.setattr(module, "_is_pid_alive", lambda _pid: True)

    saved: dict[str, object] = {}

    def _capture_state(_path, payload):
        saved.update(payload)

    monkeypatch.setattr(module, "_save_state", _capture_state)

    args = SimpleNamespace(
        json=True,
        mode="local",
        host="127.0.0.1",
        port=29813,
        port_fallback_span=10,
        wait_seconds=5,
    )
    exit_code = module._cmd_up_local(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["requested_port"] == 29813
    assert payload["port"] == 29814
    assert payload["port_fallback_used"] is True
    assert saved["port"] == 29814


def test_cmd_up_local_fails_when_no_port_available(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_skill_runnerctl_module()

    profile = SimpleNamespace(mode="local", data_dir=tmp_path / "data", agent_cache_root=tmp_path / "cache")
    monkeypatch.setattr(module, "_runtime_env", lambda: (profile, {"SKILL_RUNNER_LOCAL_BIND_HOST": "127.0.0.1"}))
    monkeypatch.setattr(module, "_command_exists", lambda _: True)
    monkeypatch.setattr(module, "_collect_local_status", lambda _args: {"service_healthy": False})
    monkeypatch.setattr(module, "_select_port_with_fallback", lambda _h, _p, _s: (None, [29813, 29814]))

    args = SimpleNamespace(
        json=True,
        mode="local",
        host="127.0.0.1",
        port=29813,
        port_fallback_span=1,
        wait_seconds=5,
    )
    exit_code = module._cmd_up_local(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert payload["requested_port"] == 29813
    assert payload["tried_ports"] == [29813, 29814]
