import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import jsonschema  # type: ignore[import-untyped]

from ..models import SkillManifest


class SchemaValidator:
    """
    Validates runtime data against JSON schemas defined in the skill manifest.

    Functions:
    - Resolves schema files relative to the skill directory.
    - Validates input/parameter/output payloads.
    - Supports mixed input sources (file + inline) for input schema.
    """

    def _load_schema(self, skill: SkillManifest, schema_key: str) -> Optional[Dict[str, Any]]:
        if not skill.path or not skill.schemas:
            return None

        rel_path = skill.schemas.get(schema_key)
        if not rel_path:
            return None

        path = skill.path / rel_path
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_schema_keys(self, skill: SkillManifest, schema_key: str) -> List[str]:
        schema = self._load_schema(skill, schema_key)
        if not schema:
            return []
        return list(schema.get("properties", {}).keys())

    def get_schema_required(self, skill: SkillManifest, schema_key: str) -> List[str]:
        schema = self._load_schema(skill, schema_key)
        if not schema:
            return []
        return list(schema.get("required", []))

    def get_input_sources(self, skill: SkillManifest) -> Dict[str, str]:
        schema = self._load_schema(skill, "input")
        if not schema:
            return {}
        properties = schema.get("properties", {})
        sources: Dict[str, str] = {}
        for key, spec in properties.items():
            if not isinstance(spec, dict):
                sources[key] = "file"
                continue
            source = spec.get("x-input-source", "file")
            if source not in ("file", "inline"):
                source = "file"
            sources[key] = source
        return sources

    def get_input_keys_by_source(
        self,
        skill: SkillManifest,
        source: str,
        *,
        required_only: bool = False,
    ) -> List[str]:
        sources = self.get_input_sources(skill)
        keys = [key for key, key_source in sources.items() if key_source == source]
        if not required_only:
            return keys
        required = set(self.get_schema_required(skill, "input"))
        return [key for key in keys if key in required]

    def has_required_file_inputs(self, skill: SkillManifest) -> bool:
        return bool(self.get_input_keys_by_source(skill, "file", required_only=True))

    def validate_schema(self, skill: SkillManifest, data: Dict[str, Any], schema_key: str) -> List[str]:
        """Generic validator for 'input', 'parameter', or 'output' schema."""
        if not skill.path or not skill.schemas:
            return []

        rel_path = skill.schemas.get(schema_key)
        if not rel_path:
            return []

        path = skill.path / rel_path
        if not path.exists():
            return [f"Schema file not found: {rel_path}"]

        try:
            with open(path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"{schema_key} validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except Exception as e:
            return [f"Schema validation failed: {str(e)}"]

    def validate_inline_input_create(self, skill: SkillManifest, inline_input: Dict[str, Any]) -> List[str]:
        """
        Validate only inline-sourced input keys at create stage.
        Required file inputs are intentionally ignored at this stage.
        """
        schema = self._load_schema(skill, "input")
        if not schema:
            return []

        all_keys = set(self.get_schema_keys(skill, "input"))
        inline_keys = set(self.get_input_keys_by_source(skill, "inline"))
        inline_required = self.get_input_keys_by_source(skill, "inline", required_only=True)
        errors: List[str] = []

        for key in inline_input.keys():
            if key not in all_keys:
                errors.append(f"input validation error: unknown input key '{key}'")
            elif key not in inline_keys:
                errors.append(
                    f"input validation error: key '{key}' is file-sourced; upload file via /upload"
                )

        properties = schema.get("properties", {})
        inline_schema = {
            "type": "object",
            "properties": {k: properties[k] for k in inline_keys if k in properties},
            "required": inline_required,
        }
        try:
            jsonschema.validate(instance=inline_input, schema=inline_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"input validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})")
        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")
        return errors

    def validate_input_for_execution(
        self,
        skill: SkillManifest,
        run_dir: Path,
        input_data: Dict[str, Any],
    ) -> List[str]:
        """
        Validate mixed input (inline + file) against full input schema before execution.
        """
        inline_input = input_data.get("input", {})
        if not isinstance(inline_input, dict):
            return ["input validation error: input must be an object"]

        errors = self.validate_inline_input_create(skill, inline_input)
        input_ctx, missing_required_files = self.build_input_context(skill, run_dir, input_data)
        if missing_required_files:
            errors.append(f"Missing required input files: {', '.join(missing_required_files)}")
        errors.extend(self.validate_schema(skill, input_ctx, "input"))
        return errors

    def validate_input(self, skill: SkillManifest, input_data: Dict[str, Any]) -> List[str]:
        """
        Legacy validator for input schema against supplied dict.
        """
        if not skill.path:
            return []

        schema_path_rel = None
        if skill.schemas and "input" in skill.schemas:
            schema_path_rel = skill.schemas["input"]

        if not schema_path_rel:
            return []

        schema_path = skill.path / schema_path_rel
        if not schema_path.exists():
            return [f"Schema file not found: {schema_path_rel}"]

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
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
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)

            jsonschema.validate(instance=output_data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Output validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except Exception as e:
            return [f"Output schema validation failed: {str(e)}"]

    def build_input_context(
        self,
        skill: SkillManifest,
        run_dir: Path,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, Any], List[str]]:
        """
        Resolve mixed input context and return (context, missing_required_files).

        - file source: resolve from uploads/<key> to absolute path
        - inline source: resolve from input_data["input"][<key>]
        """
        input_ctx: Dict[str, Any] = {}
        missing_required_files: List[str] = []
        if not skill.schemas or "input" not in skill.schemas:
            return input_ctx, missing_required_files

        inline_payload: Dict[str, Any] = {}
        if input_data and isinstance(input_data.get("input"), dict):
            inline_payload = input_data.get("input", {})

        uploads_dir = run_dir / "uploads"
        file_keys = self.get_input_keys_by_source(skill, "file")
        required_file_keys = self.get_input_keys_by_source(skill, "file", required_only=True)
        inline_keys = self.get_input_keys_by_source(skill, "inline")

        for key in file_keys:
            potential_file = uploads_dir / key
            if potential_file.exists():
                input_ctx[key] = str(potential_file.absolute())
            elif key in required_file_keys:
                missing_required_files.append(key)

        for key in inline_keys:
            if key in inline_payload:
                input_ctx[key] = inline_payload[key]

        return input_ctx, missing_required_files

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
