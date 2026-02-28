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
    assert profile.prompt_builder.engine_key == "codex"
    assert profile.session_codec.strategy == "first_json_line"


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
                "prompt_builder": {
                    "engine_key": "gemini",
                    "default_template_path": "../../../assets/templates/gemini_default.j2",
                    "fallback_inline": "fallback",
                    "merge_input_if_no_parameter_schema": True,
                    "params_json_source": "input_data",
                    "main_prompt_source": "none",
                    "main_prompt_default_template": "Execute skill {skill_id}",
                    "include_input_file_name": False,
                    "include_skill_dir": False
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
                "workspace_provisioner": {
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
                "prompt_builder": {
                    "engine_key": "codex"
                },
                "session_codec": {
                    "strategy": "first_json_line",
                    "error_message": "x"
                },
                "workspace_provisioner": {
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
                "prompt_builder": {
                    "engine_key": "codex",
                    "default_template_path": None,
                    "fallback_inline": "fallback",
                    "merge_input_if_no_parameter_schema": True,
                    "params_json_source": "combined_input_parameter",
                    "main_prompt_source": "none",
                    "main_prompt_default_template": "Execute skill {skill_id}",
                    "include_input_file_name": False,
                    "include_skill_dir": False
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
                "workspace_provisioner": {
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
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="path not found"):
        load_adapter_profile("codex", profile_path)
