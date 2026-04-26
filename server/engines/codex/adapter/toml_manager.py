import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, cast

import jsonschema  # type: ignore[import-untyped]
import tomlkit
from tomlkit.exceptions import TOMLKitError

from server.services.engine_management.runtime_profile import get_runtime_profile

_TOML_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    TOMLKitError,
    TypeError,
    ValueError,
)
_SCHEMA_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
    jsonschema.SchemaError,
)

logger = logging.getLogger(__name__)


class CodexConfigManager:
    """
    Manages Codex CLI configuration profiles.

    The final profile is composed of:
    1. Engine Defaults
    2. Skill Defaults
    3. Runtime Overrides
    4. Enforced Policy
    """

    PROFILE_NAME = "skill-runner"
    _DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "default.toml"
    _ENFORCED_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "enforced.toml"
    _SCHEMA_PATH = Path(__file__).resolve().parents[4] / "assets" / "schemas" / "codex_profile_schema.json"

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
        self.DEFAULT_CONFIG_PATH = default_config_path or self._DEFAULT_CONFIG_PATH
        self.ENFORCED_CONFIG_PATH = enforced_config_path or self._ENFORCED_CONFIG_PATH
        self.SCHEMA_PATH = schema_path or self._SCHEMA_PATH

    def ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.touch()

    def generate_profile_settings(
        self,
        skill_defaults: Dict[str, Any],
        runtime_config: Dict[str, Any],
        governed_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        final_config: Dict[str, Any] = {}
        self._deep_merge(final_config, self._load_default_profile_config())
        self._deep_merge(final_config, skill_defaults)
        self._deep_merge(final_config, runtime_config)
        if governed_config:
            self._deep_merge(final_config, governed_config)

        enforced_profile, _ = self._extract_enforced_sections(self._load_enforced_config())
        self._deep_merge(final_config, enforced_profile)

        self._validate_config(final_config)
        return final_config

    def _load_default_profile_config(self) -> Dict[str, Any]:
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
        except _TOML_LOAD_EXCEPTIONS:
            logger.exception("Error loading default codex config")
            return {}

    def _validate_config(self, config: Dict[str, Any]) -> None:
        if not self.SCHEMA_PATH.exists():
            logger.warning("Codex profile schema not found at %s", self.SCHEMA_PATH)
            return

        try:
            with open(self.SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e.message}")
        except _SCHEMA_LOAD_EXCEPTIONS as e:
            raise ValueError(f"Schema validation error: {e}")

    def _load_enforced_config(self) -> Dict[str, Any]:
        if not self.ENFORCED_CONFIG_PATH.exists():
            return {}
        try:
            with open(self.ENFORCED_CONFIG_PATH, "r", encoding="utf-8") as f:
                return tomlkit.parse(f.read())
        except _TOML_LOAD_EXCEPTIONS:
            logger.exception("Error loading enforced config")
            return {}

    def _extract_enforced_sections(
        self,
        enforced_config: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        profiles_obj = enforced_config.get("profiles", {})
        if not isinstance(profiles_obj, dict):
            profiles_obj = {}
        enforced_profile = profiles_obj.get(self.profile_name)
        if not isinstance(enforced_profile, dict):
            enforced_profile = profiles_obj.get(self.PROFILE_NAME, {})
        if not isinstance(enforced_profile, dict):
            enforced_profile = {}
        global_settings: Dict[str, Any] = {}
        for key, value in enforced_config.items():
            if key == "profiles":
                continue
            global_settings[key] = deepcopy(value)
        return dict(enforced_profile), global_settings

    def get_enforced_global_settings(self) -> Dict[str, Any]:
        _, global_settings = self._extract_enforced_sections(self._load_enforced_config())
        return global_settings

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _merge_any_mapping(self, target: Any, source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_any_mapping(target[key], value)
            else:
                target[key] = value

    def update_profile(
        self,
        settings: Dict[str, Any],
        *,
        global_settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.ensure_config_exists()

        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))

        if "profiles" not in doc:
            doc["profiles"] = tomlkit.table()

        profiles = cast(Any, doc["profiles"])

        if self.profile_name not in profiles:
            profiles[self.profile_name] = tomlkit.table()

        profile = cast(Any, profiles[self.profile_name])
        for key, value in settings.items():
            profile[key] = value

        if isinstance(global_settings, dict):
            self._merge_any_mapping(doc, global_settings)

        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    def get_profile(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))

        profiles_obj = doc.get("profiles", {})
        if not isinstance(profiles_obj, dict):
            return {}
        return profiles_obj.get(self.profile_name, {})

    def remove_profile(self, profile_name: str | None = None) -> bool:
        if not self.config_path.exists():
            return False

        with open(self.config_path, "r", encoding="utf-8") as f:
            doc = cast(Any, tomlkit.parse(f.read()))

        profiles_obj = doc.get("profiles")
        if not isinstance(profiles_obj, dict):
            return False

        target_profile = (profile_name or self.profile_name).strip()
        if not target_profile or target_profile not in profiles_obj:
            return False

        del profiles_obj[target_profile]

        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        return True
