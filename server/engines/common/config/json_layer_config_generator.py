from pathlib import Path
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

class ConfigGenerator:
    """
    Utility for generating JSON configuration files from multiple layers.
    
    Used by adapters (e.g., GeminiAdapter) to build `settings.json` by merging:
    1. Base defaults
    2. Skill-specific defaults
    3. User overrides
    4. System enforced policies
    """
    def __init__(self):
        self.schemas_dir = Path(__file__).resolve().parents[3] / "assets" / "schemas"

    def deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merges two dictionaries.
        """
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                base[k] = self.deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any], path: str = ""):
        """
        Validates config against schema. Recursively checks keys and types.
        Schema values should be type strings: "str", "int", "bool", "float", "list", "dict".
        """
        type_map: Dict[str, type[Any] | tuple[type[Any], ...]] = {
            "str": str,
            "int": int,
            "float": (float, int),
            "bool": bool,
            "list": list,
            "dict": dict
        }

        for k, v in config.items():
            current_path = f"{path}.{k}" if path else k
            
            if k not in schema:
                logger.warning(f"Config warning: Key '{current_path}' not found in schema.")
                continue # Skip validation for unknown keys, or strict mode? User said "illegal config check", maybe strict.
                         # For now, just log warning to allow forward compatibility.

            expected_type_str = schema[k]
            
            # Handle nested dicts
            if isinstance(expected_type_str, dict):
                if not isinstance(v, dict):
                    raise ValueError(f"Config error: '{current_path}' expected dict, got {type(v).__name__}")
                self.validate_config(v, expected_type_str, current_path)
                continue
            
            # Handle basic types
            expected_type = type_map.get(expected_type_str)
            if expected_type is not None and not isinstance(v, expected_type):
                 raise ValueError(f"Config error: '{current_path}' expected {expected_type_str}, got {type(v).__name__}")

    def generate_config(self, schema_name: str, config_layers: list[Dict[str, Any]], output_path: Path) -> Path:
        """
        Merges config layers (in order) and writes to output_path after validation.
        config_layers: [base_defaults, skill_defaults, user_overrides]
        """
        
        # 1. Load Schema
        schema_path = self.schemas_dir / schema_name
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema {schema_name} not found")
            
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # 2. Merge Layers
        final_config: Dict[str, Any] = {}
        for layer in config_layers:
            final_config = self.deep_merge(final_config, layer)
            
        # 3. Validate
        self.validate_config(final_config, schema)
        
        # 4. Write
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(final_config, f, indent=2)
            
        return output_path

config_generator = ConfigGenerator()
