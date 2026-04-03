from __future__ import annotations

import json
from pathlib import Path

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

    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert settings_path == run_dir / ".claude" / "settings.json"
    assert payload["env"]["ANTHROPIC_MODEL"] == "claude-sonnet-4-6"
    assert payload["permissions"]["defaultMode"] == "bypassPermissions"
    assert payload["includeGitInstructions"] is False
    assert payload["sandbox"]["enabled"] is True
    assert payload["sandbox"]["autoAllowBashIfSandboxed"] is True
    assert payload["sandbox"]["allowUnsandboxedCommands"] is True
    assert payload["sandbox"]["filesystem"]["allowWrite"] == [
        "//tmp",
        f"//{run_dir.resolve()}",
    ]
    assert f"//{agent_home.resolve()}" in payload["sandbox"]["filesystem"]["denyWrite"]
    assert "effort" not in payload


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

    settings_path = adapter.config_composer.compose(ctx)
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["sandbox"]["enabled"] is False
    assert payload["sandbox"]["filesystem"]["allowWrite"] == [
        "//tmp",
        f"//{run_dir.resolve()}",
    ]
