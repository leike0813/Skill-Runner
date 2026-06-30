import pytest
import os
from pathlib import Path
from server.config import config, get_cfg_defaults

def test_default_config_loading():
    """Verify default values are loaded correctly."""
    cfg = get_cfg_defaults()
    assert cfg.SYSTEM.ROOT == str(Path(__file__).parent.parent.parent)
    assert cfg.SYSTEM.DATA_DIR == str(Path(cfg.SYSTEM.ROOT) / "data")
    assert cfg.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS == 1200
    assert cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.ENABLED is True
    assert (
        cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.SOURCE_REPOSITORY
        == "https://github.com/leike0813/zotero-agents"
    )
    assert (
        cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.SOURCE_BRANCH
        == "host-bridge/zotero-bridge-cli-bundle"
    )
    assert cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.INTERVAL_SEC == 86400
    assert cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.STARTUP_DELAY_SEC == 30
    assert cfg.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.TIMEOUT_SEC == 30

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
