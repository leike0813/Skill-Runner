from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.runtime.adapter.common.profile_loader import (
    load_adapter_profile,
    validate_adapter_profiles,
)


def test_load_adapter_profile_success() -> None:
    profile_path = Path("server/engines/codex/adapter/adapter_profile.json")
    profile = load_adapter_profile("codex", profile_path)
    assert profile.engine == "codex"
    assert profile.prompt_builder.skill_invoke_line_template == "${{ skill.id }}"
    assert profile.prompt_builder.body_prefix_extra_block == ""
    assert profile.prompt_builder.body_suffix_extra_block == ""
    assert profile.session_codec.strategy == "first_json_line"
    assert profile.command_defaults.start[:2] == ("--skip-git-repo-check", "--json")
    assert profile.ui_shell.command_id == "codex-tui"
    assert profile.ui_shell.label == "Codex TUI"
    assert profile.cli_management.package == "@openai/codex"
    assert "codex" in profile.cli_management.binary_candidates
    assert profile.command_features.inject_output_schema_cli is True
    assert profile.structured_output.mode == "compat_translate"
    assert profile.structured_output.cli_schema_strategy == "path_schema_artifact"
    assert profile.structured_output.prompt_contract_strategy == "compat_summary"
    assert profile.structured_output.payload_canonicalizer == "payload_union_object_canonicalizer"


def test_load_adapter_profile_defaults_missing_command_features_to_disabled(tmp_path: Path) -> None:
    bootstrap_path = tmp_path / "bootstrap.json"
    default_path = tmp_path / "default.json"
    enforced_path = tmp_path / "enforced.json"
    schema_path = tmp_path / "settings.schema.json"
    manifest_path = tmp_path / "manifest.json"
    models_root = tmp_path / "models"
    bootstrap_path.write_text("{}", encoding="utf-8")
    default_path.write_text("{}", encoding="utf-8")
    enforced_path.write_text("{}", encoding="utf-8")
    schema_path.write_text("{}", encoding="utf-8")
    models_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"engine": "codex", "snapshots": []}),
        encoding="utf-8",
    )

    profile_path = tmp_path / "adapter_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "engine": "codex",
                "provider_contract": {
                    "multi_provider": False,
                    "canonical_provider_id": "openai",
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "${{ skill.id }}",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": "",
                },
                "session_codec": {
                    "strategy": "first_json_line",
                    "error_message": "missing",
                    "error_prefix": "SESSION_RESUME_FAILED: codex",
                    "required_type": "thread.started",
                    "id_field": "thread_id",
                    "recursive_key": None,
                    "fallback_text_finder": None,
                    "json_lines_finder": None,
                    "regex_pattern": None,
                },
                "attempt_workspace": {
                    "workspace_subdir": ".codex",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": False,
                    "unknown_fallback": False,
                },
                "config_assets": {
                    "bootstrap_path": str(bootstrap_path),
                    "default_path": str(default_path),
                    "enforced_path": str(enforced_path),
                    "settings_schema_path": str(schema_path),
                    "skill_defaults_path": None,
                },
                "model_catalog": {
                    "mode": "manifest",
                    "manifest_path": str(manifest_path),
                    "models_root": str(models_root),
                    "seed_path": None,
                },
                "command_defaults": {
                    "start": ["--json"],
                    "resume": ["--json"],
                    "ui_shell": [],
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop",
                },
                "ui_shell": {
                    "command_id": "codex-tui",
                    "label": "Codex TUI",
                    "trust_bootstrap_parent": True,
                    "sandbox_arg": "--sandbox",
                    "retry_without_sandbox_on_early_exit": False,
                    "sandbox_probe_strategy": "codex_landlock",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "none",
                    "runtime_override_strategy": "none",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None,
                    },
                },
                "cli_management": {
                    "package": "@openai/codex",
                    "binary_candidates": ["codex"],
                    "credential_imports": [
                        {
                            "source": "auth.json",
                            "target_relpath": ".codex/auth.json",
                        }
                    ],
                    "credential_policy": {
                        "mode": "all_of_sources",
                        "sources": ["auth.json"],
                        "settings_validator": None,
                    },
                    "resume_probe": {
                        "help_hints": ["resume"],
                        "dynamic_args": ["exec", "resume", "--help"],
                    },
                    "layout": {
                        "extra_dirs": [".codex"],
                        "bootstrap_target_relpath": ".codex/config.toml",
                        "bootstrap_format": "text",
                        "normalize_strategy": None,
                    },
                },
                "parser_auth_patterns": {
                    "rules": [],
                },
            }
        ),
        encoding="utf-8",
    )

    profile = load_adapter_profile("codex", profile_path)

    assert profile.command_features.inject_output_schema_cli is False
    assert profile.structured_output.mode == "noop"
    assert profile.structured_output.cli_schema_strategy == "noop"


def test_load_adapter_profile_engine_mismatch(tmp_path: Path) -> None:
    bootstrap_path = tmp_path / "bootstrap.json"
    default_path = tmp_path / "default.json"
    enforced_path = tmp_path / "enforced.json"
    schema_path = tmp_path / "settings.schema.json"
    manifest_path = tmp_path / "manifest.json"
    models_root = tmp_path / "models"
    bootstrap_path.write_text("{}", encoding="utf-8")
    default_path.write_text("{}", encoding="utf-8")
    enforced_path.write_text("{}", encoding="utf-8")
    schema_path.write_text("{}", encoding="utf-8")
    models_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"engine": "gemini", "snapshots": []}),
        encoding="utf-8",
    )

    profile_path = tmp_path / "adapter_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "engine": "gemini",
                "provider_contract": {
                    "multi_provider": True,
                    "canonical_provider_id": None,
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "/{{ skill.id }} invoke",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": ""
                },
                "session_codec": {
                    "strategy": "json_recursive_key",
                    "error_message": "missing",
                    "error_prefix": None,
                    "required_type": None,
                    "id_field": None,
                    "recursive_key": "session_id",
                    "fallback_text_finder": "find_session_id_in_text",
                    "json_lines_finder": None,
                    "regex_pattern": None
                },
                "attempt_workspace": {
                    "workspace_subdir": ".gemini",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": True,
                    "unknown_fallback": False
                },
                "config_assets": {
                    "bootstrap_path": str(bootstrap_path),
                    "default_path": str(default_path),
                    "enforced_path": str(enforced_path),
                    "settings_schema_path": str(schema_path),
                    "skill_defaults_path": "assets/gemini_settings.json"
                },
                "model_catalog": {
                    "mode": "manifest",
                    "manifest_path": str(manifest_path),
                    "models_root": str(models_root),
                    "seed_path": None
                },
                "command_defaults": {
                    "start": ["--yolo"],
                    "resume": ["--yolo"],
                    "ui_shell": ["--sandbox", "--approval-mode", "default"]
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop"
                },
                "ui_shell": {
                    "command_id": "gemini-tui",
                    "label": "Gemini TUI",
                    "trust_bootstrap_parent": True,
                    "sandbox_arg": "--sandbox",
                    "retry_without_sandbox_on_early_exit": True,
                    "sandbox_probe_strategy": "gemini_container",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "gemini_api_key_disables_sandbox",
                    "runtime_override_strategy": "gemini_ui_shell",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None
                    }
                },
                "cli_management": {
                    "package": "@google/gemini-cli",
                    "binary_candidates": ["gemini"],
                    "credential_imports": [
                        {
                            "source": "oauth_creds.json",
                            "target_relpath": ".gemini/oauth_creds.json"
                        }
                    ],
                    "credential_policy": {
                        "mode": "all_of_sources",
                        "sources": ["oauth_creds.json"],
                        "settings_validator": None
                    },
                    "resume_probe": {
                        "help_hints": ["--resume"],
                        "dynamic_args": ["--resume", "probe-session", "--help"]
                    },
                    "layout": {
                        "extra_dirs": [".gemini"],
                        "bootstrap_target_relpath": ".gemini/settings.json",
                        "bootstrap_format": "json",
                        "normalize_strategy": None
                    }
                },
                "parser_auth_patterns": {
                    "rules": []
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="engine mismatch"):
        load_adapter_profile("codex", profile_path)


def test_validate_adapter_profiles_fail_fast(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "engine": "codex",
                "provider_contract": {
                    "multi_provider": False,
                    "canonical_provider_id": "openai",
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "${{ skill.id }}",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": ""
                },
                "session_codec": {
                    "strategy": "first_json_line",
                    "error_message": "x"
                },
                "attempt_workspace": {
                    "workspace_subdir": ".codex",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": False,
                    "unknown_fallback": False
                },
                "config_assets": {
                    "bootstrap_path": "",
                    "default_path": "",
                    "enforced_path": ""
                },
                "model_catalog": {
                    "mode": "manifest",
                    "manifest_path": None,
                    "models_root": None,
                    "seed_path": None
                },
                "command_defaults": {
                    "start": [],
                    "resume": [],
                    "ui_shell": []
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop"
                },
                "ui_shell": {
                    "command_id": "codex-tui",
                    "label": "Codex TUI",
                    "trust_bootstrap_parent": True,
                    "sandbox_arg": "--sandbox",
                    "retry_without_sandbox_on_early_exit": False,
                    "sandbox_probe_strategy": "codex_landlock",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "none",
                    "runtime_override_strategy": "none",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="validation failed"):
        validate_adapter_profiles({"codex": bad})


def test_load_adapter_profile_fails_when_config_path_missing(tmp_path: Path) -> None:
    profile_path = tmp_path / "adapter_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "engine": "codex",
                "provider_contract": {
                    "multi_provider": False,
                    "canonical_provider_id": "openai",
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "${{ skill.id }}",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": ""
                },
                "session_codec": {
                    "strategy": "first_json_line",
                    "error_message": "missing",
                    "error_prefix": "x",
                    "required_type": "thread.started",
                    "id_field": "thread_id",
                    "recursive_key": None,
                    "fallback_text_finder": None,
                    "json_lines_finder": None,
                    "regex_pattern": None
                },
                "attempt_workspace": {
                    "workspace_subdir": ".codex",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": False,
                    "unknown_fallback": False
                },
                "config_assets": {
                    "bootstrap_path": str(tmp_path / "missing.toml"),
                    "default_path": str(tmp_path / "missing_default.toml"),
                    "enforced_path": str(tmp_path / "missing_enforced.toml"),
                    "settings_schema_path": str(tmp_path / "missing_schema.json"),
                    "skill_defaults_path": "assets/codex_config.toml"
                },
                "model_catalog": {
                    "mode": "manifest",
                    "manifest_path": str(tmp_path / "missing_manifest.json"),
                    "models_root": str(tmp_path / "missing_models"),
                    "seed_path": None
                },
                "command_defaults": {
                    "start": ["--json"],
                    "resume": ["--json"],
                    "ui_shell": []
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop"
                },
                "ui_shell": {
                    "command_id": "codex-tui",
                    "label": "Codex TUI",
                    "trust_bootstrap_parent": True,
                    "sandbox_arg": "--sandbox",
                    "retry_without_sandbox_on_early_exit": False,
                    "sandbox_probe_strategy": "codex_landlock",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "none",
                    "runtime_override_strategy": "none",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None
                    }
                },
                "cli_management": {
                    "package": "@openai/codex",
                    "binary_candidates": ["codex"],
                    "credential_imports": [
                        {
                            "source": "auth.json",
                            "target_relpath": ".codex/auth.json"
                        }
                    ],
                    "credential_policy": {
                        "mode": "all_of_sources",
                        "sources": ["auth.json"],
                        "settings_validator": None
                    },
                    "resume_probe": {
                        "help_hints": ["resume"],
                        "dynamic_args": ["exec", "resume", "--help"]
                    },
                    "layout": {
                        "extra_dirs": [".codex"],
                        "bootstrap_target_relpath": ".codex/config.toml",
                        "bootstrap_format": "text",
                        "normalize_strategy": None
                    }
                },
                "parser_auth_patterns": {
                    "rules": []
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="path not found"):
        load_adapter_profile("codex", profile_path)


def test_load_adapter_profile_fails_when_credential_target_is_absolute(tmp_path: Path) -> None:
    bootstrap_path = tmp_path / "bootstrap.toml"
    default_path = tmp_path / "default.toml"
    enforced_path = tmp_path / "enforced.toml"
    manifest_path = tmp_path / "manifest.json"
    models_root = tmp_path / "models"
    bootstrap_path.write_text("x=1", encoding="utf-8")
    default_path.write_text("x=1", encoding="utf-8")
    enforced_path.write_text("x=1", encoding="utf-8")
    manifest_path.write_text(json.dumps({"engine": "codex", "snapshots": []}), encoding="utf-8")
    models_root.mkdir(parents=True, exist_ok=True)

    profile_path = tmp_path / "adapter_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "engine": "codex",
                "provider_contract": {
                    "multi_provider": False,
                    "canonical_provider_id": "openai",
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "${{ skill.id }}",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": ""
                },
                "session_codec": {
                    "strategy": "first_json_line",
                    "error_message": "missing",
                    "error_prefix": "x",
                    "required_type": "thread.started",
                    "id_field": "thread_id",
                    "recursive_key": None,
                    "fallback_text_finder": None,
                    "json_lines_finder": None,
                    "regex_pattern": None
                },
                "attempt_workspace": {
                    "workspace_subdir": ".codex",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": False,
                    "unknown_fallback": False
                },
                "config_assets": {
                    "bootstrap_path": str(bootstrap_path),
                    "default_path": str(default_path),
                    "enforced_path": str(enforced_path),
                    "settings_schema_path": None,
                    "skill_defaults_path": "assets/codex_config.toml"
                },
                "model_catalog": {
                    "mode": "manifest",
                    "manifest_path": str(manifest_path),
                    "models_root": str(models_root),
                    "seed_path": None
                },
                "command_defaults": {
                    "start": ["--json"],
                    "resume": ["--json"],
                    "ui_shell": []
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop"
                },
                "ui_shell": {
                    "command_id": "codex-tui",
                    "label": "Codex TUI",
                    "trust_bootstrap_parent": True,
                    "sandbox_arg": "--sandbox",
                    "retry_without_sandbox_on_early_exit": False,
                    "sandbox_probe_strategy": "codex_landlock",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "none",
                    "runtime_override_strategy": "none",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None
                    }
                },
                "cli_management": {
                    "package": "@openai/codex",
                    "binary_candidates": ["codex"],
                    "credential_imports": [
                        {
                            "source": "auth.json",
                            "target_relpath": "/tmp/auth.json"
                        }
                    ],
                    "credential_policy": {
                        "mode": "all_of_sources",
                        "sources": ["auth.json"],
                        "settings_validator": None
                    },
                    "resume_probe": {
                        "help_hints": ["resume"],
                        "dynamic_args": ["exec", "resume", "--help"]
                    },
                    "layout": {
                        "extra_dirs": [".codex"],
                        "bootstrap_target_relpath": ".codex/config.toml",
                        "bootstrap_format": "text",
                        "normalize_strategy": None
                    }
                },
                "parser_auth_patterns": {
                    "rules": []
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="must be relative"):
        load_adapter_profile("codex", profile_path)
