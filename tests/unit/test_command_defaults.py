from __future__ import annotations

from server.runtime.adapter.common.command_defaults import merge_cli_args


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
