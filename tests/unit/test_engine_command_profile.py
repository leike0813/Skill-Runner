from __future__ import annotations

import json
from pathlib import Path

from server.services.engine_command_profile import EngineCommandProfile, merge_cli_args


def test_resolve_args_returns_empty_when_profile_missing(tmp_path: Path) -> None:
    profile = EngineCommandProfile(profile_path=tmp_path / "missing.json")
    assert profile.resolve_args(engine="codex", action="start") == []


def test_resolve_args_reads_engine_action_list(tmp_path: Path) -> None:
    payload = {
        "codex": {
            "start": ["--json", "-p", "skill-runner"],
            "resume": ["--json", "-p", "skill-runner"],
        },
        "gemini": {"start": ["--yolo"]},
    }
    profile_path = tmp_path / "engine_command_profiles.json"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    profile = EngineCommandProfile(profile_path=profile_path)

    assert profile.resolve_args(engine="codex", action="start") == ["--json", "-p", "skill-runner"]
    assert profile.resolve_args(engine="gemini", action="resume") == []
    assert profile.resolve_args(engine="iflow", action="start") == []


def test_merge_cli_args_explicit_overrides_default_option_value() -> None:
    defaults = ["--json", "--model", "default-model", "-p", "skill-runner"]
    explicit = ["--model", "custom-model", "--temperature", "0.1"]

    merged = merge_cli_args(defaults, explicit)

    assert merged == ["--json", "-p", "skill-runner", "--model", "custom-model", "--temperature", "0.1"]


def test_merge_cli_args_explicit_overrides_equals_style_option() -> None:
    defaults = ["--json", "--profile=skill-runner", "--sandbox=workspace-write"]
    explicit = ["--profile=custom", "--temperature", "0.5"]

    merged = merge_cli_args(defaults, explicit)

    assert "--json" in merged
    assert "--sandbox=workspace-write" in merged
    assert "--profile=skill-runner" not in merged
    assert "--profile=custom" in merged
