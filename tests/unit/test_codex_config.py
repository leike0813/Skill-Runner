import pytest
import tomlkit
from pathlib import Path
from server.engines.codex.adapter.config.toml_manager import CodexConfigManager

@pytest.fixture
def temp_config_file(tmp_path):
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    return config_file

def test_ensure_config_exists(temp_config_file):
    # Setup
    manager = CodexConfigManager(config_path=temp_config_file)
    
    # Execution
    manager.ensure_config_exists()
    
    # Assertion
    assert temp_config_file.exists()
    assert temp_config_file.read_text() == ""

def test_update_profile_creates_new_profile(temp_config_file):
    # Setup
    manager = CodexConfigManager(config_path=temp_config_file)
    settings = {"model": "gpt-4", "model_provider": "openai"}
    
    # Execution
    manager.update_profile(settings)
    
    # Assertion
    with open(temp_config_file, "r") as f:
        doc = tomlkit.parse(f.read())
        
    assert "profiles" in doc
    assert "skill-runner" in doc["profiles"]
    assert doc["profiles"]["skill-runner"]["model"] == "gpt-4"

def test_update_profile_preserves_comments(temp_config_file):
    # Setup
    temp_config_file.write_text("# User comment\n[profiles.other]\nkey = 'value'\n")
    manager = CodexConfigManager(config_path=temp_config_file)
    settings = {"model": "gpt-5"}
    
    # Execution
    manager.update_profile(settings)
    
    # Assertion
    content = temp_config_file.read_text()
    assert "# User comment" in content
    assert "[profiles.other]" in content
    
    with open(temp_config_file, "r") as f:
        doc = tomlkit.parse(f.read())
    
    assert doc["profiles"]["skill-runner"]["model"] == "gpt-5"
