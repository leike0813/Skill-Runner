from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agent_harness.config import HarnessConfig
from agent_harness.errors import HarnessError
from agent_harness.runtime import HarnessLaunchRequest, HarnessResumeRequest, HarnessRuntime
from agent_harness.storage import resolve_next_attempt_paths
from server.services.runtime_profile import RuntimeProfile


def _build_profile(root: Path) -> RuntimeProfile:
    return RuntimeProfile(
        mode="local",
        platform="linux",
        data_dir=root / "data",
        agent_cache_root=root / "cache",
        agent_home=root / "cache" / "agent-home",
        npm_prefix=root / "cache" / "npm",
        uv_cache_dir=root / "cache" / "uv-cache",
        uv_project_environment=root / "cache" / "uv-venv",
    )


class _DummyHarnessRuntime(HarnessRuntime):
    class _FakeAdapter:
        def __init__(self, engine: str, owner: "_DummyHarnessRuntime") -> None:
            self.engine = engine
            self.owner = owner

        def _construct_config(self, skill, run_dir: Path, options):
            self.owner.config_injection_calls.append(
                {
                    "engine": self.engine,
                    "skill": skill,
                    "run_dir": run_dir,
                    "options": dict(options),
                }
            )
            if self.owner.fail_config_injection:
                raise RuntimeError("config injection failed")
            suffix = "config.toml" if self.engine == "codex" else "settings.json"
            return run_dir / f".{self.engine}" / suffix

        def build_start_command(
            self,
            *,
            prompt: str,
            options,
            passthrough_args=None,
            use_profile_defaults=True,
        ):
            if self.engine == "opencode":
                raise RuntimeError("ENGINE_CAPABILITY_UNAVAILABLE: adapter.execute")
            args = list(passthrough_args or [])
            return [f"/usr/bin/{self.engine}", *args]

        def build_resume_command(
            self,
            prompt: str,
            options,
            session_handle,
            passthrough_args=None,
            use_profile_defaults=True,
        ):
            if self.engine == "opencode":
                raise RuntimeError("ENGINE_CAPABILITY_UNAVAILABLE: adapter.execute")
            flags = [
                token
                for token in list(passthrough_args or [])
                if isinstance(token, str) and token.startswith("-")
            ]
            return [
                f"/usr/bin/{self.engine}",
                "exec",
                "resume",
                *flags,
                session_handle.handle_value,
                prompt,
            ]

        def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
            stdout = stdout_raw.decode("utf-8", errors="replace")
            diagnostics: list[str] = []
            session_id = None
            assistant_messages = []
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("type") == "thread.started":
                    thread_id = payload.get("thread_id")
                    if isinstance(thread_id, str) and thread_id.strip():
                        session_id = thread_id.strip()
                if isinstance(payload, dict) and payload.get("type") == "item.completed":
                    item = payload.get("item")
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            assistant_messages.append({"text": text, "raw_ref": None})
            if not assistant_messages and stdout.strip():
                diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")
            return {
                "parser": "codex_ndjson",
                "confidence": 0.95 if assistant_messages else 0.6,
                "session_id": session_id,
                "assistant_messages": assistant_messages,
                "raw_rows": [],
                "diagnostics": diagnostics,
                "structured_types": [],
            }

    def __init__(self, config: HarnessConfig) -> None:
        super().__init__(config)
        self.commands: list[list[str]] = []
        self.stdout = ""
        self.stderr = ""
        self.exit_code = 0
        self.config_injection_calls: list[dict[str, object]] = []
        self.fail_config_injection = False

    def _resolve_adapter(self, engine: str):
        return self._FakeAdapter(engine, self)

    def _ensure_executable_path(self, *, engine: str, command: list[str]) -> Path:
        return Path(command[0]) if command else Path(f"/usr/bin/{engine}")

    def _run_command(
        self,
        *,
        engine: str,
        command: list[str],
        run_dir: Path,
        translate_level: int = 0,
        attempt_paths=None,
        stdin_text: str = "",
    ) -> tuple[int, str, str, str]:
        self.commands.append(list(command))
        return self.exit_code, self.stdout, self.stderr, stdin_text


def test_start_passthrough_translate_and_attempt_artifacts(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-1"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
    )

    result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "hello"],
            translate_level=2,
        )
    )

    assert runtime.commands[0] == ["/usr/bin/codex", "exec", "--json", "-p", "hello"]
    assert len(runtime.config_injection_calls) == 1
    injected = runtime.config_injection_calls[0]
    assert injected["engine"] == "codex"
    assert injected["options"] == {
        "__harness_mode": True,
        "__codex_profile_name": "skill-runner-harness",
    }
    injected_skill = injected["skill"]
    assert hasattr(injected_skill, "id")
    assert getattr(injected_skill, "id") == "harness-config-bootstrap"
    assert getattr(injected_skill, "path") is None
    assert result["translate_level"] == 2
    assert result["status"] == "waiting_user"
    assert result["attempt_number"] == 1
    assert isinstance(result["handle"], str) and len(result["handle"]) == 8
    run_dir = Path(result["run_dir"])
    assert (run_dir / ".audit" / "meta.1.json").exists()
    assert (run_dir / ".audit" / "stdout.1.log").exists()
    assert (run_dir / ".audit" / "stderr.1.log").exists()
    assert (run_dir / ".audit" / "pty-output.1.log").exists()
    assert not any(path.name.startswith("fd-trace") for path in (run_dir / ".audit").iterdir())


def test_harness_registers_and_cleans_trust_for_codex(tmp_path: Path, monkeypatch) -> None:
    class _TrustSpy:
        def __init__(self) -> None:
            self.register_calls: list[tuple[str, Path]] = []
            self.remove_calls: list[tuple[str, Path]] = []

        def register_run_folder(self, engine: str, run_dir: Path) -> None:
            self.register_calls.append((engine, run_dir))

        def remove_run_folder(self, engine: str, run_dir: Path) -> None:
            self.remove_calls.append((engine, run_dir))

    trust_spy = _TrustSpy()
    monkeypatch.setattr("agent_harness.runtime.run_folder_trust_manager", trust_spy)
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'

    result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "trust"],
            translate_level=1,
        )
    )
    run_dir = Path(result["run_dir"])
    assert trust_spy.register_calls == [("codex", run_dir)]
    assert trust_spy.remove_calls == [("codex", run_dir)]


def test_harness_does_not_register_trust_for_iflow(tmp_path: Path, monkeypatch) -> None:
    class _TrustSpy:
        def __init__(self) -> None:
            self.register_calls: list[tuple[str, Path]] = []
            self.remove_calls: list[tuple[str, Path]] = []

        def register_run_folder(self, engine: str, run_dir: Path) -> None:
            self.register_calls.append((engine, run_dir))

        def remove_run_folder(self, engine: str, run_dir: Path) -> None:
            self.remove_calls.append((engine, run_dir))

    trust_spy = _TrustSpy()
    monkeypatch.setattr("agent_harness.runtime.run_folder_trust_manager", trust_spy)
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'

    runtime.start(
        HarnessLaunchRequest(
            engine="iflow",
            passthrough_args=["--json", "-p", "trust"],
            translate_level=1,
        )
    )
    assert trust_spy.register_calls == []
    assert trust_spy.remove_calls == []


def test_run_selector_reuse_increments_attempt(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-rs"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
    )
    first = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "hello"],
            translate_level=1,
            run_selector="manual-run",
        )
    )
    second = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "hello-again"],
            translate_level=1,
            run_selector="manual-run",
        )
    )

    assert first["run_dir"] == second["run_dir"]
    assert first["attempt_number"] == 1
    assert second["attempt_number"] == 2
    run_dir = Path(first["run_dir"])
    assert (run_dir / ".audit" / "meta.1.json").exists()
    assert (run_dir / ".audit" / "meta.2.json").exists()


def test_resume_uses_handle_and_inherits_translate_level(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-resume"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"first"}}\n'
    )
    start_result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "--skip-git-repo-check", "-p", "first"],
            translate_level=1,
        )
    )
    handle = start_result["handle"]
    assert isinstance(handle, str)

    runtime.stdout = (
        '{"type":"item.completed","item":{"type":"agent_message","text":"second"}}\n'
        "__SKILL_DONE__\n"
    )
    resumed = runtime.resume(HarnessResumeRequest(handle=handle, message="second turn"))

    assert resumed["translate_level"] == 1
    assert resumed["status"] == "succeeded"
    assert resumed["completion"]["reason_code"] == "DONE_MARKER_FOUND"
    resume_command = runtime.commands[-1]
    assert resume_command[:4] == ["/usr/bin/codex", "exec", "resume", "--json"]
    assert "session-resume" in resume_command
    assert "second turn" in resume_command


def test_harness_injects_project_and_fixture_skills(tmp_path: Path) -> None:
    project_skill = tmp_path / "skills" / "project-skill"
    fixture_skill = tmp_path / "tests" / "fixtures" / "skills" / "fixture-skill"
    project_skill.mkdir(parents=True, exist_ok=True)
    fixture_skill.mkdir(parents=True, exist_ok=True)
    (project_skill / "SKILL.md").write_text("# project skill\n", encoding="utf-8")
    (fixture_skill / "SKILL.md").write_text("# fixture skill\n", encoding="utf-8")

    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
        project_root=tmp_path,
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-inject"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
    )

    result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "inject"],
            translate_level=1,
        )
    )
    run_dir = Path(result["run_dir"])
    project_target = run_dir / ".codex" / "skills" / "project-skill" / "SKILL.md"
    fixture_target = run_dir / ".codex" / "skills" / "fixture-skill" / "SKILL.md"
    assert project_target.exists()
    assert fixture_target.exists()
    assert "Runtime Completion Contract" in project_target.read_text(encoding="utf-8")
    assert "Runtime Completion Contract" in fixture_target.read_text(encoding="utf-8")

    meta_path = run_dir / ".audit" / "meta.1.json"
    meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
    injection = meta_payload.get("skill_injection")
    assert isinstance(injection, dict)
    assert injection.get("skill_count") == 2
    assert sorted(injection.get("skills", [])) == ["fixture-skill", "project-skill"]
    config_injection = meta_payload.get("config_injection")
    assert isinstance(config_injection, dict)
    assert config_injection.get("engine") == "codex"
    assert config_injection.get("profile_name") == "skill-runner-harness"


def test_opencode_is_capability_gated(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    with pytest.raises(HarnessError) as exc:
        runtime.start(HarnessLaunchRequest(engine="opencode", passthrough_args=[], translate_level=0))
    assert exc.value.code == "ENGINE_CAPABILITY_UNAVAILABLE"


def test_engine_config_injection_failure_is_structured_error(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.fail_config_injection = True

    with pytest.raises(HarnessError) as exc:
        runtime.start(
            HarnessLaunchRequest(
                engine="codex",
                passthrough_args=["exec", "--json", "-p", "hello"],
                translate_level=1,
            )
        )
    assert exc.value.code == "ENGINE_CONFIG_INJECTION_FAILED"


def test_conformance_report_contains_required_summary(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-report"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"report body"}}\n'
        "__SKILL_DONE__\n"
    )

    result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "report"],
            translate_level=3,
        )
    )
    report_path = Path(result["audit"]["report"])
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["parser_profile"] == "codex_ndjson"
    assert report_payload["completion"]["state"] == "completed"
    assert "fcmp_summary" in report_payload
    assert isinstance(result["view"], str)
    assert "### Simulated Frontend View (Markdown)" in result["view"]
    assert "- Assistant: report body" in result["view"]


def test_translate_level3_waiting_user_suppresses_default_english_prompt(tmp_path: Path) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-waiting"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"need more input"}}\n'
    )

    result = runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "waiting"],
            translate_level=3,
        )
    )

    assert result["status"] == "waiting_user"
    assert isinstance(result["view"], str)
    assert "System: (请输入下一步指令...)" in result["view"]
    assert "System: Provide next user turn" not in result["view"]


def test_runtime_markers_wrap_translate_output_once(tmp_path: Path, capsys) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = _DummyHarnessRuntime(config)
    runtime.stdout = (
        '{"type":"thread.started","thread_id":"session-wrap"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"wrapped"}}\n'
        "__SKILL_DONE__\n"
    )

    runtime.start(
        HarnessLaunchRequest(
            engine="codex",
            passthrough_args=["exec", "--json", "-p", "wrapped"],
            translate_level=3,
        )
    )
    captured = capsys.readouterr()
    run_id_line = "[agent:codex] run_id="
    run_dir_line = "[agent:codex] run_dir="
    executable_line = "[agent:codex] executable=/usr/bin/codex"
    passthrough_line = '[agent:codex] passthrough=["exec", "--json", "-p", "wrapped"]'
    translate_line = "[agent:codex] translate_mode=3"
    injected = "[agent:codex] injected_skills="
    config_roots = "[agent:codex] config_roots="
    begin = "[agent:codex] ---------------- runtime begin ----------------"
    end = "[agent:codex] ---------------- runtime end ----------------"
    assert run_id_line in captured.err
    assert run_dir_line in captured.err
    assert executable_line in captured.err
    assert passthrough_line in captured.err
    assert translate_line in captured.err
    assert injected in captured.err
    assert config_roots in captured.err
    assert captured.err.index(run_id_line) < captured.err.index(begin)
    assert captured.err.index(config_roots) < captured.err.index(begin)
    assert captured.err.index(injected) < captured.err.index(begin)
    assert captured.err.count(begin) == 1
    assert captured.err.count(end) == 1
    assert "### Simulated Frontend View (Markdown)" in captured.out


def test_run_command_requires_script_binary(tmp_path: Path, monkeypatch) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = HarnessRuntime(config)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("agent_harness.runtime.shutil.which", lambda *_args, **_kwargs: None)
    with pytest.raises(HarnessError) as exc:
        runtime._run_command(engine="codex", command=["/usr/bin/codex", "exec"], run_dir=run_dir)
    assert exc.value.code == "PTY_RUNTIME_UNAVAILABLE"


def test_run_command_with_log_out_does_not_append_dev_null(tmp_path: Path, monkeypatch) -> None:
    config = HarnessConfig(
        runtime_profile=_build_profile(tmp_path),
        run_root=tmp_path / "harness_runs",
    )
    runtime = HarnessRuntime(config)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    attempt_paths = resolve_next_attempt_paths(run_dir)

    monkeypatch.setattr("agent_harness.runtime.shutil.which", lambda *_args, **_kwargs: "/usr/bin/script")
    captured: dict[str, object] = {}

    class _Result:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr("agent_harness.runtime.subprocess.run", _fake_run)

    runtime._run_command(
        engine="codex",
        command=["/usr/bin/codex", "exec"],
        run_dir=run_dir,
        attempt_paths=attempt_paths,
    )
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--log-out" in cmd
    assert "/dev/null" not in cmd
