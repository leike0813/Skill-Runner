import pytest
import tomlkit
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from server.engines.codex.adapter.config.toml_manager import CodexConfigManager

# Mocks
@pytest.fixture
def mock_enforced_config(tmp_path):
    config_file = tmp_path / "codex_enforced.toml"
    content = """
    [profiles.skill-runner]
    approval_policy = "never"
    sandbox_mode = "workspace-write"
    
    [features]
    shell_tool = false
    """
    config_file.write_text(content)
    return config_file

@pytest.fixture
def mock_default_config(tmp_path):
    config_file = tmp_path / "codex_default.toml"
    content = """
    [profiles.skill-runner]
    model = "gpt-5.1-codex-mini"
    model_provider = "openai"
    model_reasoning_effort = "low"
    """
    config_file.write_text(content)
    return config_file

@pytest.fixture
def mock_schema(tmp_path):
    schema_file = tmp_path / "codex_profile_schema.json"
    schema = {
        "type": "object",
        "properties": {
             "model": {"type": "string"},
             "model_provider": {"type": "string"},
             "approval_policy": {"type": "string", "enum": ["never", "on-request"]},
             "sandbox_mode": {"type": "string", "enum": ["read-only", "workspace-write", "danger-full-access"]}
        },
        "required": ["model"]
    }
    schema_file.write_text(json.dumps(schema))
    return schema_file

@pytest.fixture
def manager(tmp_path, mock_enforced_config, mock_default_config, mock_schema):
    mgr = CodexConfigManager(config_path=tmp_path / "config.toml")
    # Patch paths to use temp files
    mgr.DEFAULT_CONFIG_PATH = mock_default_config
    mgr.ENFORCED_CONFIG_PATH = mock_enforced_config
    mgr.SCHEMA_PATH = mock_schema
    return mgr

def test_fusion_precedence(manager):
    """
    Verify precedence: Enforced > Runtime > Skill Defaults > Engine Defaults
    """
    # 1. Skill Defaults
    skill_defaults = {
        "model": "gpt-3.5",
        "approval_policy": "on-request", # Should be overridden by Enforced
        "model_reasoning_effort": "medium",
    }
    
    # 2. Runtime Config
    runtime_config = {
        "model": "gpt-4", # Should override skill default
        "model_provider": "anthropic", # Should override default
        "sandbox_mode": "read-only" # Should be overridden by Enforced
    }
    
    # 3. Enforced Config (High Priority) loaded from file automatically by _load_enforced_config
    # We rely on the real file loading logic pointing to our mock file
    
    # Execution
    final_config = manager.generate_profile_settings(skill_defaults, runtime_config)
        
    # Assertions
    
    # Validation 1: Runtime overrides Skill default
    assert final_config["model"] == "gpt-4"
    assert final_config["model_provider"] == "anthropic"
    assert final_config["model_reasoning_effort"] == "medium"
    
    # Validation 2: Enforced overrides Runtime AND Skill default
    assert final_config["approval_policy"] == "never" # Enforced overrides skill "on-request"
    assert final_config["sandbox_mode"] == "workspace-write" # Enforced overrides runtime "read-only"

def test_deep_merge_behavior(manager):
    """Verify deep merge applies to nested dictionaries if we had them in profile."""
    skill_defaults = {
        "model": "gpt-4",
        "features": {
            "shell_tool": True,
            "nested": {"a": 0}
        }
    }
    runtime_config = {
        "features": {
            "shell_tool": True,
            "nested": {"a": 1, "b": 2}
        }
    }
    enforced_config = {
        "profiles": {
            "skill-runner": {
                "features": {
                    "shell_tool": False,
                    "nested": {"a": 2}
                }
            }
        }
    }

    with patch.object(manager, "_load_enforced_config", return_value=enforced_config):
        final_config = manager.generate_profile_settings(skill_defaults, runtime_config)

    assert final_config["features"]["shell_tool"] is False
    assert final_config["features"]["nested"]["a"] == 2
    assert final_config["features"]["nested"]["b"] == 2

def test_validation_failure(manager):
    """Verify schema validation rejects invalid values."""
    skill_defaults = {"model": "gpt-4"}
    runtime_config = {"sandbox_mode": "invalid-mode"} # Invalid enum
    
    # Patch enforced config to be empty so it doesn't override our invalid runtime value
    with patch.object(manager, '_load_enforced_config', return_value={}):
        with pytest.raises(ValueError, match="validation failed"):
             manager.generate_profile_settings(skill_defaults, runtime_config)


def test_custom_profile_falls_back_to_default_enforced_section(tmp_path):
    mgr = CodexConfigManager(
        config_path=tmp_path / "config.toml",
        profile_name="skill-runner-harness",
    )
    enforced_config = {
        "profiles": {
            "skill-runner": {
                "approval_policy": "never",
                "sandbox_mode": "workspace-write",
            }
        }
    }
    with patch.object(mgr, "_load_enforced_config", return_value=enforced_config):
        with patch.object(mgr, "_validate_config", return_value=None):
            final_config = mgr.generate_profile_settings({"model": "gpt-5"}, {})
    assert final_config["approval_policy"] == "never"
    assert final_config["sandbox_mode"] == "workspace-write"


def test_engine_default_used_when_skill_and_runtime_missing(tmp_path, mock_schema, mock_default_config):
    mgr = CodexConfigManager(config_path=tmp_path / "config.toml")
    mgr.SCHEMA_PATH = mock_schema
    mgr.DEFAULT_CONFIG_PATH = mock_default_config

    with patch.object(mgr, "_load_enforced_config", return_value={}):
        final_config = mgr.generate_profile_settings({}, {})

    assert final_config["model"] == "gpt-5.1-codex-mini"
    assert final_config["model_provider"] == "openai"
    assert final_config["model_reasoning_effort"] == "low"
