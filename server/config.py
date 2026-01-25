"""
Configuration Loader.

This module initializes the global configuration object (`config`) used throughout
the application. It leverages `yacs` to provide a hierarchical, dot-accessible
configuration structure defined in `server.core_config`.

Usage:
    from server.config import config
    print(config.SYSTEM.ROOT)
"""

import os
import logging
from server.core_config import get_cfg_defaults

# Load default configuration
config = get_cfg_defaults()

# Override from config.yaml if present (Optional, for user overrides)
# user_config_path = "config.yaml"
# if os.path.exists(user_config_path):
#    config.merge_from_file(user_config_path)

# Freeze config to prevent accidental changes during runtime.
# This ensures immutability of the global config state.
config.freeze()

# Backward compatibility alias (if any module imports Config class, they will break)
# But checked usage: most import `from server.config import config`.
# The attributes in YACS conform to the structure in core_config.py.
# Access: config.SYSTEM.SKILLS_DIR
# Old access: config.SKILLS_DIR
# This IS A BREAKING CHANGE.
# I need to ensure backward compatibility or refactor all usages.
# The user prompt said: "refactor configuration management... use yacs".
# I should update usages to `config.SYSTEM.SKILLS_DIR` OR map them.
# Let's try to map them for now or update the CfgNode structure to be flat if that helps?
# No, hierarchical is better. I will update usages in the codebase if they are few.
# Based on `grep_search`, `config.SKILLS_DIR` and `config.RUNS_DIR` are likely used.
# I will check usages first.

logger = logging.getLogger(__name__)
