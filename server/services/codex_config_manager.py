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
    1. Engine Defaults (from `server/assets/configs/codex/default.toml`)
    2. Skill Defaults (from `assets/codex_config.toml`)
    3. Runtime Overrides (from API request)
    4. Enforced Policy (security strictures)
    """
    
    PROFILE_NAME = "skill-runner"
    _DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "assets" / "configs" / "codex" / "default.toml"
    _ENFORCED_CONFIG_PATH = Path(__file__).parent.parent / "assets" / "configs" / "codex" / "enforced.toml"
    _SCHEMA_PATH = Path(__file__).parent.parent / "assets" / "schemas" / "codex_profile_schema.json"
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        profile_name: Optional[str] = None,
        default_config_path: Optional[Path] = None,
        enforced_config_path: Optional[Path] = None,
        schema_path: Optional[Path] = None,
    ):
        profile = get_runtime_profile()
        self.config_path = config_path or profile.agent_home / ".codex" / "config.toml"
        normalized_profile_name = (profile_name or self.PROFILE_NAME).strip()
        self.profile_name = normalized_profile_name or self.PROFILE_NAME
        # Keep instance-level names for backward-compatible tests/overrides.
        self.DEFAULT_CONFIG_PATH = default_config_path or self._DEFAULT_CONFIG_PATH
        self.ENFORCED_CONFIG_PATH = enforced_config_path or self._ENFORCED_CONFIG_PATH
        self.SCHEMA_PATH = schema_path or self._SCHEMA_PATH
        
    def ensure_config_exists(self) -> None:
        """Create empty config file if it doesn't exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.touch()

    def generate_profile_settings(self, skill_defaults: Dict[str, Any], runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates the final profile configuration by merging layers:
        1. Engine Defaults (from assets/configs/codex/default.toml)
        2. Skill Defaults (from assets/codex_config.toml)
        3. Runtime Config (User overrides from API)
        4. Enforced Config (Built-in mandatory defaults)
        
        Validation is applied to the final result.
        """
        # 1. Start with Engine Defaults (lowest precedence)
        final_config: Dict[str, Any] = {}
        self._deep_merge(final_config, self._load_default_profile_config())
        
        # 2. Merge Skill Defaults
        self._deep_merge(final_config, skill_defaults)

        # 3. Merge Runtime Config (User overrides)
        self._deep_merge(final_config, runtime_config)
        
        # 4. Merge Enforced Config (Mandatory overrides)
        enforced_config = self._load_enforced_config()
        # Prefer enforced section that matches current profile name.
        # Fallback to default profile to keep backward compatibility when custom
        # profile sections are not present in enforced config.
        profiles_obj = enforced_config.get("profiles", {})
        if not isinstance(profiles_obj, dict):
            profiles_obj = {}
        enforced_profile = profiles_obj.get(self.profile_name)
        if not isinstance(enforced_profile, dict):
            enforced_profile = profiles_obj.get(self.PROFILE_NAME, {})
        if not isinstance(enforced_profile, dict):
            enforced_profile = {}
        self._deep_merge(final_config, enforced_profile)
        
        # 5. Validate
        self._validate_config(final_config)
        
        return final_config

    def _load_default_profile_config(self) -> Dict[str, Any]:
        """Load engine-level default profile configuration."""
        if not self.DEFAULT_CONFIG_PATH.exists():
            return {}
        try:
            with open(self.DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                parsed = tomlkit.parse(f.read())
            profiles_obj = parsed.get("profiles", {})
            if isinstance(profiles_obj, dict):
                profile_cfg = profiles_obj.get(self.profile_name)
                if not isinstance(profile_cfg, dict):
                    profile_cfg = profiles_obj.get(self.PROFILE_NAME)
                if isinstance(profile_cfg, dict):
                    return dict(profile_cfg)
            if isinstance(parsed, dict):
                return dict(parsed)
            return {}
        except Exception:
            logger.exception("Error loading default codex config")
            return {}

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
        Injects or updates the configured profile section in the user's config.toml.
        Preserves comments and formatting using tomlkit.
        """
        self.ensure_config_exists()
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))
            
        if "profiles" not in doc:
            doc["profiles"] = tomlkit.table()
            
        profiles = cast(Any, doc["profiles"])
        
        if self.profile_name not in profiles:
            profiles[self.profile_name] = tomlkit.table()
            
        profile = cast(Any, profiles[self.profile_name])
        
        # Update settings in the profile
        for key, value in settings.items():
            profile[key] = value
            
        # Write back atomically
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    def get_profile(self) -> Dict[str, Any]:
        """Retrieve the current settings for the configured profile."""
        if not self.config_path.exists():
            return {}
            
        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))
            
        profiles_obj = doc.get("profiles", {})
        if not isinstance(profiles_obj, dict):
            return {}
        return profiles_obj.get(self.profile_name, {})


logger = logging.getLogger(__name__)
