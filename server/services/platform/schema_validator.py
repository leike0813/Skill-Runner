import json
import logging
from pathlib import Path, PurePosixPath
from typing import Dict, Any, List, Optional

import jsonschema  # type: ignore[import-untyped]

from server.models import SkillManifest
from server.services.skill.skill_asset_resolver import load_resolved_json, resolve_schema_asset

_SCHEMA_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)
_SCHEMA_VALIDATE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    jsonschema.SchemaError,
    TypeError,
    ValueError,
)

logger = logging.getLogger(__name__)


def _normalize_upload_relative_path(raw_value: str) -> str:
    normalized = PurePosixPath(raw_value.strip().replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("file input path must be relative to uploads/")
    for part in normalized.parts:
        if part in {"", ".", ".."}:
            raise ValueError("file input path must stay within uploads/")
    rel_path = normalized.as_posix()
    if not rel_path:
        raise ValueError("file input path is required")
    return rel_path


class SchemaValidator:
    """
    Validates runtime data against JSON schemas defined in the skill manifest.

    Functions:
    - Resolves schema files relative to the skill directory.
    - Validates input/parameter/output payloads.
    - Supports mixed input sources (file + inline) for input schema.
    """

    def _load_schema(self, skill: SkillManifest, schema_key: str) -> Optional[Dict[str, Any]]:
        resolution = resolve_schema_asset(skill, schema_key)
        if resolution.issue_source == "declared" and resolution.used_fallback:
            logger.warning(
                "Schema declaration fallback used: skill=%s schema=%s declared=%s fallback=%s issue=%s",
                skill.id,
                schema_key,
                resolution.declared_relpath,
                resolution.fallback_relpath,
                resolution.issue_code,
            )
        return load_resolved_json(resolution.path)

    def load_output_schema(self, skill: SkillManifest) -> Optional[Dict[str, Any]]:
        return self._load_schema(skill, "output")

    def is_output_schema_too_permissive(self, skill: SkillManifest) -> bool:
        schema = self.load_output_schema(skill)
        if not isinstance(schema, dict):
            return False
        if schema.get("type") != "object":
            return False
        required_obj = schema.get("required")
        required_fields: List[str] = []
        if isinstance(required_obj, list):
            required_fields = [
                field.strip()
                for field in required_obj
                if isinstance(field, str) and field.strip()
            ]
        if required_fields:
            return False
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return True
        for prop_schema in properties.values():
            if not isinstance(prop_schema, dict):
                return False
            x_type = str(prop_schema.get("x-type") or "").strip().lower()
            if x_type not in {"artifact", "file"}:
                return False
        return True

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
        resolution = resolve_schema_asset(skill, schema_key)
        path = resolution.path
        if path is None:
            label = resolution.fallback_relpath or resolution.declared_relpath or schema_key
            return [f"Schema file not found: {label}"]

        try:
            schema = load_resolved_json(path)
            if not isinstance(schema, dict):
                label = path.relative_to(skill.path).as_posix() if skill.path else path.name
                return [f"Schema file not found: {label}"]
            jsonschema.validate(instance=data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"{schema_key} validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except _SCHEMA_VALIDATE_EXCEPTIONS as e:
            return [f"Schema validation failed: {str(e)}"]

    def validate_inline_input_create(self, skill: SkillManifest, inline_input: Dict[str, Any]) -> List[str]:
        """
        Validate request input keys at create stage.
        Inline keys are schema-validated; file keys are validated as uploads-relative paths.
        Required file inputs remain optional here because strict-key compatibility fallback is preserved.
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
                value = inline_input.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"input validation error: key '{key}' must be a non-empty uploads-relative path"
                    )
                    continue
                try:
                    _normalize_upload_relative_path(value)
                except ValueError as exc:
                    errors.append(f"input validation error: key '{key}' {str(exc)}")

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
        except _SCHEMA_VALIDATE_EXCEPTIONS as e:
            errors.append(f"Schema validation failed: {str(e)}")
        return errors

    def validate_declared_file_input_paths(
        self,
        skill: SkillManifest,
        input_data: Dict[str, Any],
        uploads_dir: Path,
    ) -> List[str]:
        errors: List[str] = []
        if resolve_schema_asset(skill, "input").path is None:
            return errors
        inline_payload: Dict[str, Any] = {}
        if isinstance(input_data.get("input"), dict):
            inline_payload = input_data.get("input", {})
        for key in self.get_input_keys_by_source(skill, "file"):
            raw_value = inline_payload.get(key)
            if raw_value is None:
                continue
            if not isinstance(raw_value, str) or not raw_value.strip():
                errors.append(
                    f"input validation error: key '{key}' must be a non-empty uploads-relative path"
                )
                continue
            try:
                rel_path = _normalize_upload_relative_path(raw_value)
            except ValueError as exc:
                errors.append(f"input validation error: key '{key}' {str(exc)}")
                continue
            target = (uploads_dir / rel_path).resolve()
            try:
                target.relative_to(uploads_dir.resolve())
            except ValueError:
                errors.append(f"input validation error: key '{key}' escapes uploads root")
                continue
            if not target.exists() or not target.is_file():
                errors.append(
                    f"input validation error: uploaded file not found for key '{key}' at '{rel_path}'"
                )
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
        resolution = resolve_schema_asset(skill, "input")
        schema_path = resolution.path
        if schema_path is None:
            label = resolution.fallback_relpath or resolution.declared_relpath or "input"
            return [f"Schema file not found: {label}"]

        try:
            schema = load_resolved_json(schema_path)
            if not isinstance(schema, dict):
                return [f"Schema file not found: {schema_path.name}"]

            jsonschema.validate(instance=input_data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Input validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except _SCHEMA_VALIDATE_EXCEPTIONS as e:
            return [f"Schema validation failed: {str(e)}"]

    def validate_output(self, skill: SkillManifest, output_data: Dict[str, Any]) -> List[str]:
        """
        Validates output_data against the skill's output schema.
        Returns a list of error messages.
        """
        if not skill.path:
            return ["Output schema missing: skill path not set"]

        resolution = resolve_schema_asset(skill, "output")
        schema_path = resolution.path
        if schema_path is None:
            label = resolution.fallback_relpath or resolution.declared_relpath or "output"
            return [f"Output schema file missing: {label}"]

        try:
            schema = self.load_output_schema(skill)
            if not isinstance(schema, dict):
                return [f"Output schema file missing: {schema_path.relative_to(skill.path).as_posix()}"]
            jsonschema.validate(instance=output_data, schema=schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Output validation error: {e.message} (Path: {'/'.join(str(x) for x in e.path)})"]
        except _SCHEMA_VALIDATE_EXCEPTIONS as e:
            return [f"Output schema validation failed: {str(e)}"]

    def build_input_context(
        self,
        skill: SkillManifest,
        run_dir: Path,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, Any], List[str]]:
        """
        Resolve mixed input context and return (context, missing_required_files).

        - file source: resolve from request-declared uploads-relative path, else fallback to uploads/<key>
        - inline source: resolve from input_data["input"][<key>]
        """
        input_ctx: Dict[str, Any] = {}
        missing_required_files: List[str] = []
        if resolve_schema_asset(skill, "input").path is None:
            return input_ctx, missing_required_files

        inline_payload: Dict[str, Any] = {}
        if input_data and isinstance(input_data.get("input"), dict):
            inline_payload = input_data.get("input", {})

        uploads_dir = run_dir / "uploads"
        file_keys = self.get_input_keys_by_source(skill, "file")
        required_file_keys = self.get_input_keys_by_source(skill, "file", required_only=True)
        inline_keys = self.get_input_keys_by_source(skill, "inline")

        for key in file_keys:
            declared_path = inline_payload.get(key)
            if isinstance(declared_path, str) and declared_path.strip():
                try:
                    normalized_rel = _normalize_upload_relative_path(declared_path)
                    potential_file = (uploads_dir / normalized_rel).resolve()
                    potential_file.relative_to(uploads_dir.resolve())
                except (ValueError, OSError):
                    potential_file = None
                if potential_file is not None and potential_file.exists() and potential_file.is_file():
                    input_ctx[key] = str(potential_file.absolute())
                    continue
                if key in required_file_keys:
                    missing_required_files.append(key)
                continue

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
        if resolve_schema_asset(skill, "parameter").path is None:
            return param_ctx

        param_keys = self.get_schema_keys(skill, "parameter")
        raw_params = input_data.get("parameter", {})
        for key in param_keys:
            if key in raw_params:
                param_ctx[key] = raw_params[key]

        return param_ctx


schema_validator = SchemaValidator()
