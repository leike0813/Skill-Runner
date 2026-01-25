import pytest
import os
from pathlib import Path
from server.core_config import get_cfg_defaults
from server.config import config

def test_default_config_loading():
    """Verify default values are loaded correctly."""
    cfg = get_cfg_defaults()
    assert cfg.SYSTEM.ROOT == str(Path(__file__).parent.parent.parent)
    assert cfg.SYSTEM.DATA_DIR == str(Path(cfg.SYSTEM.ROOT) / "data")
    assert cfg.GEMINI.DEFAULT_PROMPT_TEMPLATE.endswith("gemini_default.j2")

def test_config_singleton():
    """Verify the singleton config object is loaded and frozen."""
    assert config.SYSTEM.ROOT
    # Attempt to modify frozen config should raise error
    with pytest.raises(Exception):
        # Checking if it's frozen
         if config.is_frozen():
             config.SYSTEM.ROOT = "new_root"
    
    assert config.is_frozen()

def test_path_resolution():
    """Verify paths are strings but point to valid locations (logically)."""
    root = Path(config.SYSTEM.ROOT)
    assert root.exists()
    assert (root / "server").exists()
