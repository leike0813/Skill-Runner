import os
import json
import tomlkit
import jsonschema  # type: ignore[import-untyped]
import logging
from pathlib import Path
from typing import Dict, Any, Optional, cast
from .runtime_profile import get_runtime_profile

class CodexConfigManager:
    """
    Manages Codex CLI Configuration Profiles.
    
    Rationale:
    Codex CLI uses a global configuration file (`~/.codex/config.toml`). To allow
    skills to have isolated or preset configurations, this manager injects a 
    dedicated profile (`[profiles.skill-runner]`) into the user's config.
    
    The final profile is composed of:
    1. Skill Defaults (from `assets/codex_settings.toml`)
    2. Runtime Overrides (from API request)
    3. Enforced Policy (security strictures)
    """
    
    PROFILE_NAME = "skill-runner"
    ENFORCED_CONFIG_PATH = Path(__file__).parent.parent / "assets" / "configs" / "codex_enforced.toml"
    SCHEMA_PATH = Path(__file__).parent.parent / "assets" / "schemas" / "codex_profile_schema.json"
    
    def __init__(self, config_path: Optional[Path] = None):
        profile = get_runtime_profile()
        self.config_path = config_path or profile.agent_home / ".codex" / "config.toml"
        
    def ensure_config_exists(self) -> None:
        """Create empty config file if it doesn't exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.touch()

    def generate_profile_settings(self, skill_defaults: Dict[str, Any], runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates the final profile configuration by merging layers:
        1. Skill Defaults (from assets/codex_settings.json)
        2. Runtime Config (User overrides from API)
        3. Enforced Config (Built-in mandatory defaults)
        
        Validation is applied to the final result.
        """
        # 1. Start with Skill Defaults
        # ensure deep copy if needed, but shallow copy is usually fine for top level
        final_config = skill_defaults.copy()
        
        # 2. Merge Runtime Config (User overrides)
        self._deep_merge(final_config, runtime_config)
        
        # 3. Merge Enforced Config (Mandatory overrides)
        enforced_config = self._load_enforced_config()
        # We only care about the [profiles.skill-runner] section from enforced config
        enforced_profile = enforced_config.get("profiles", {}).get(self.PROFILE_NAME, {})
        self._deep_merge(final_config, enforced_profile)
        
        # 4. Validate
        self._validate_config(final_config)
        
        return final_config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration against the JSON schema."""
        if not self.SCHEMA_PATH.exists():
            logger.warning("Codex profile schema not found at %s", self.SCHEMA_PATH)
            return
            
        try:
            with open(self.SCHEMA_PATH, "r") as f:
                schema = json.load(f)
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e.message}")
        except Exception as e:
            raise ValueError(f"Schema validation error: {e}")

    def _load_enforced_config(self) -> Dict[str, Any]:
        """Load the built-in enforced configuration."""
        if not self.ENFORCED_CONFIG_PATH.exists():
            return {}
        try:
            with open(self.ENFORCED_CONFIG_PATH, "r") as f:
                return tomlkit.parse(f.read())
        except Exception as e:
            logger.exception("Error loading enforced config")
            return {}

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Helper to recursively merge dictionaries."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def update_profile(self, settings: Dict[str, Any]) -> None:
        """
        Injects or updates the [profiles.skill-runner] section in the user's config.toml.
        Preserves comments and formatting using tomlkit.
        """
        self.ensure_config_exists()
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))
            
        if "profiles" not in doc:
            doc["profiles"] = tomlkit.table()
            
        profiles = cast(Any, doc["profiles"])
        
        if self.PROFILE_NAME not in profiles:
            profiles[self.PROFILE_NAME] = tomlkit.table()
            
        profile = cast(Any, profiles[self.PROFILE_NAME])
        
        # Update settings in the profile
        for key, value in settings.items():
            profile[key] = value
            
        # Write back atomically
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    def get_profile(self) -> Dict[str, Any]:
        """Retrieve the current settings for the skill-runner profile."""
        if not self.config_path.exists():
            return {}
            
        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))
            
        return doc.get("profiles", {}).get(self.PROFILE_NAME, {})


logger = logging.getLogger(__name__)
