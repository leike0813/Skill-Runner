import json
import jsonschema  # type: ignore[import-untyped]
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..models import SkillManifest

class SchemaValidator:
    """
    Validates runtime data against JSON schemas defined in the skill manifest.
    
    Functions:
    - Resolves schema files relative to the skill directory.
    - Validates inputs ('parameters' and 'files' existence).
    - Validates outputs against 'output' schema.
    """
    def get_schema_keys(self, skill: SkillManifest, schema_key: str) -> List[str]:
        """Returns top-level property keys for a given schema type (files/parameters)."""
        if not skill.path or not skill.schemas:
            return []
            
        rel_path = skill.schemas.get(schema_key)
        if not rel_path:
            return []
            
        path = skill.path / rel_path
        if not path.exists():
            return []
            
        try:
            with open(path, "r") as f:
                schema = json.load(f)
            return list(schema.get("properties", {}).keys())
        except:
            return []

    def get_schema_required(self, skill: SkillManifest, schema_key: str) -> List[str]:
        """Returns required keys defined for a given schema type."""
        if not skill.path or not skill.schemas:
            return []

        rel_path = skill.schemas.get(schema_key)
        if not rel_path:
            return []

        path = skill.path / rel_path
        if not path.exists():
            return []

        try:
            with open(path, "r") as f:
                schema = json.load(f)
            return list(schema.get("required", []))
        except:
            return []

    def validate_schema(self, skill: SkillManifest, data: Dict[str, Any], schema_key: str) -> List[str]:
        """Generic validator for 'files' or 'parameters' schema."""
        if not skill.path or not skill.schemas:
            return []
            
        rel_path = skill.schemas.get(schema_key)
        if not rel_path:
             return []
        
        path = skill.path / rel_path
        if not path.exists():
            return [f"Schema file not found: {rel_path}"]
            
        try:
            with open(path, "r") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"{schema_key} validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except Exception as e:
            return [f"Schema validation failed: {str(e)}"]

    def validate_input(self, skill: SkillManifest, input_data: Dict[str, Any]) -> List[str]:
        """
        Legacy/Unified validator. Checks inputs against 'input' schema if present.
        """
        if not skill.path:
            return []
            
        # Resolve input schema path from runner.json definition
        # Typically runner.json has "schemas": {"input": "assets/input.schema.json", ...}
        schema_path_rel = None
        if skill.schemas and "input" in skill.schemas:
            schema_path_rel = skill.schemas["input"]
        
        if not schema_path_rel:
            return []
            
        schema_path = skill.path / schema_path_rel
        if not schema_path.exists():
            return [f"Schema file not found: {schema_path_rel}"]
            
        try:
            with open(schema_path, "r") as f:
                schema = json.load(f)
            
            jsonschema.validate(instance=input_data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Input validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except Exception as e:
            return [f"Schema validation failed: {str(e)}"]

    def validate_output(self, skill: SkillManifest, output_data: Dict[str, Any]) -> List[str]:
        """
        Validates output_data against the skill's output schema.
        Returns a list of error messages.
        """
        if not skill.path:
            return ["Output schema missing: skill path not set"]
            
        schema_path_rel = None
        if skill.schemas and "output" in skill.schemas:
            schema_path_rel = skill.schemas["output"]
        
        if not schema_path_rel:
            return ["Output schema missing: schema entry not found"]
            
        schema_path = skill.path / schema_path_rel
        if not schema_path.exists():
            return [f"Output schema file missing: {schema_path_rel}"]
            
        try:
            with open(schema_path, "r") as f:
                schema = json.load(f)
            
            jsonschema.validate(instance=output_data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Output validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except Exception as e:
            return [f"Output schema validation failed: {str(e)}"]

    def build_input_context(self, skill: SkillManifest, run_dir: Path) -> tuple[Dict[str, str], List[str]]:
        """Resolve input file paths and return (context, missing_required)."""
        input_ctx: Dict[str, str] = {}
        missing_required: List[str] = []
        if not skill.schemas or "input" not in skill.schemas:
            return input_ctx, missing_required

        uploads_dir = run_dir / "uploads"
        file_keys = self.get_schema_keys(skill, "input")
        required_keys = self.get_schema_required(skill, "input")

        for key in file_keys:
            potential_file = uploads_dir / key
            if potential_file.exists():
                input_ctx[key] = str(potential_file.absolute())
            elif key in required_keys:
                missing_required.append(key)

        return input_ctx, missing_required

    def build_parameter_context(self, skill: SkillManifest, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter values based on schema keys."""
        param_ctx: Dict[str, Any] = {}
        if not skill.schemas or "parameter" not in skill.schemas:
            return param_ctx

        param_keys = self.get_schema_keys(skill, "parameter")
        raw_params = input_data.get("parameter", {})
        for key in param_keys:
            if key in raw_params:
                param_ctx[key] = raw_params[key]

        return param_ctx

schema_validator = SchemaValidator()
