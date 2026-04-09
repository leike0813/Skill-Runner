from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.claude.adapter.sandbox_probe import (
    ClaudeSandboxProbeResult,
    write_claude_sandbox_probe,
)
from server.models.skill import SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext


def test_claude_config_composer_writes_headless_run_settings_with_run_local_sandbox(
    tmp_path: Path,
) -> None:
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=True,
            status="available",
            warning_code=None,
            message="Claude sandbox runtime probe succeeded.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = AdapterExecutionContext(
        skill=SkillManifest(
            id="demo",
            path=skill_dir,
            entrypoint={},
        ),
        run_dir=run_dir,
        input_data={},
        options={
            "model": "claude-sonnet-4-6",
            "model_reasoning_effort": "high",
        },
    )

    assert adapter.config_composer is not None
    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert settings_path == run_dir / ".claude" / "settings.json"
    assert payload["env"]["ANTHROPIC_MODEL"] == "claude-sonnet-4-6"
    assert payload["env"]["CLAUDE_CODE_DISABLE_1M_CONTEXT"] == "1"
    assert payload["permissions"]["defaultMode"] == "bypassPermissions"
    assert payload["includeGitInstructions"] is False
    assert payload["effortLevel"] == "high"
    assert payload["sandbox"]["enabled"] is True
    assert payload["sandbox"]["autoAllowBashIfSandboxed"] is True
    assert payload["sandbox"]["allowUnsandboxedCommands"] is True
    assert payload["sandbox"]["filesystem"]["allowWrite"] == [
        "//tmp",
        f"//{run_dir.resolve()}",
    ]
    assert f"//{agent_home.resolve()}" in payload["sandbox"]["filesystem"]["denyWrite"]


def test_claude_config_composer_enables_1m_context_for_official_models(
    tmp_path: Path,
) -> None:
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=True,
            status="available",
            warning_code=None,
            message="Claude sandbox runtime probe succeeded.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = AdapterExecutionContext(
        skill=SkillManifest(
            id="demo",
            path=skill_dir,
            entrypoint={},
        ),
        run_dir=run_dir,
        input_data={},
        options={"model": "sonnet[1m]"},
    )

    assert adapter.config_composer is not None
    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["env"]["ANTHROPIC_MODEL"] == "sonnet[1m]"
    assert payload["env"]["CLAUDE_CODE_DISABLE_1M_CONTEXT"] == "0"


def test_claude_config_composer_custom_provider_1m_mode_uses_root_model_and_default_sonnet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=True,
            status="available",
            warning_code=None,
            message="Claude sandbox runtime probe succeeded.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )
    resolve_calls: list[tuple[str, str]] = []
    def _resolve_model(engine: str, model_spec: str):
        resolve_calls.append((engine, model_spec))
        if engine == "claude" and model_spec == "bailian/qwen3.5-plus[1m]":
            return SimpleNamespace(
                provider_id="bailian",
                model="qwen3.5-plus",
                api_key="sk-provider",
                base_url="https://bailian.example/v1",
            )
        return None

    monkeypatch.setattr(
        "server.engines.claude.adapter.config_composer.engine_custom_provider_service.resolve_model",
        _resolve_model,
    )

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = AdapterExecutionContext(
        skill=SkillManifest(
            id="demo",
            path=skill_dir,
            entrypoint={},
        ),
        run_dir=run_dir,
        input_data={},
        options={"model": "bailian/qwen3.5-plus[1m]"},
    )

    assert adapter.config_composer is not None
    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["model"] == "sonnet[1m]"
    assert payload["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-provider"
    assert payload["env"]["ANTHROPIC_BASE_URL"] == "https://bailian.example/v1"
    assert payload["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "qwen3.5-plus"
    assert payload["env"]["CLAUDE_CODE_DISABLE_1M_CONTEXT"] == "0"
    assert "ANTHROPIC_MODEL" not in payload["env"]
    assert resolve_calls == [("claude", "bailian/qwen3.5-plus[1m]")]


def test_claude_config_composer_merges_runtime_sandbox_allowwrite_with_headless_defaults(
    tmp_path: Path,
) -> None:
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=True,
            status="available",
            warning_code=None,
            message="Claude sandbox runtime probe succeeded.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    extra_write_dir = tmp_path / "extra-write"
    ctx = AdapterExecutionContext(
        skill=SkillManifest(
            id="demo",
            path=skill_dir,
            entrypoint={},
        ),
        run_dir=run_dir,
        input_data={},
        options={
            "claude_config": {
                "sandbox": {
                    "filesystem": {
                        "allowWrite": [f"//{extra_write_dir.resolve()}"],
                    }
                }
            }
        },
    )

    assert adapter.config_composer is not None
    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["sandbox"]["filesystem"]["allowWrite"] == [
        f"//{extra_write_dir.resolve()}",
        "//tmp",
        f"//{run_dir.resolve()}",
    ]


def test_claude_config_composer_disables_headless_sandbox_when_bootstrap_probe_unavailable(
    tmp_path: Path,
) -> None:
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=False,
            status="unavailable",
            warning_code="CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE",
            message="Claude sandbox runtime unavailable: Failed RTM_NEWADDR.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = AdapterExecutionContext(
        skill=SkillManifest(
            id="demo",
            path=skill_dir,
            entrypoint={},
        ),
        run_dir=run_dir,
        input_data={},
        options={},
    )

    assert adapter.config_composer is not None
    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["sandbox"]["enabled"] is False
    assert payload["sandbox"]["filesystem"]["allowWrite"] == [
        "//tmp",
        f"//{run_dir.resolve()}",
    ]
