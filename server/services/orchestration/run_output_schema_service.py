from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

from server.models import SkillManifest
from server.runtime.adapter.common.output_schema_cli import (
    RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH,
    TARGET_OUTPUT_SCHEMA_RELPATH,
)
from server.services.skill.skill_asset_resolver import load_resolved_json, resolve_schema_asset
from server.services.skill.skill_patch_output_schema import (
    build_interactive_pending_contract_note,
    build_output_contract_details_markdown,
)


logger = logging.getLogger(__name__)

REQUEST_INPUT_TARGET_OUTPUT_SCHEMA_PATH = "target_output_schema_path_first_attempt"


@dataclass(frozen=True)
class RunOutputSchemaMaterialization:
    business_schema: dict[str, Any] | None
    machine_schema: dict[str, Any] | None
    schema_path: Path | None
    schema_relpath: str | None
    prompt_contract_markdown: str


class RunOutputSchemaService:
    """Build and materialize the run-scoped target output schema artifacts."""

    def materialize(
        self,
        *,
        skill: SkillManifest,
        execution_mode: str,
        run_dir: Path,
    ) -> RunOutputSchemaMaterialization:
        business_schema = self._load_business_schema(skill)
        if business_schema is None:
            return RunOutputSchemaMaterialization(
                business_schema=None,
                machine_schema=None,
                schema_path=None,
                schema_relpath=None,
                prompt_contract_markdown="",
            )

        final_schema = self._build_final_wrapper_schema(business_schema)
        machine_schema = (
            self._build_interactive_union_schema(final_schema)
            if self._normalize_execution_mode(execution_mode) == "interactive"
            else final_schema
        )
        schema_path = self._artifact_path(run_dir)
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_relpath = schema_path.relative_to(run_dir).as_posix()
        prompt_contract_markdown = self.build_prompt_contract_markdown(
            final_schema=final_schema,
            schema_relpath=schema_relpath,
            execution_mode=execution_mode,
        )

        self._write_json_atomic(schema_path, machine_schema)
        self._append_request_input_audit_fields(
            run_dir=run_dir,
            fields={
                REQUEST_INPUT_TARGET_OUTPUT_SCHEMA_PATH: schema_relpath,
            },
        )

        return RunOutputSchemaMaterialization(
            business_schema=business_schema,
            machine_schema=machine_schema,
            schema_path=schema_path,
            schema_relpath=schema_relpath,
            prompt_contract_markdown=prompt_contract_markdown,
        )

    def build_run_option_fields(self, *, run_dir: Path) -> dict[str, str]:
        schema_path = self._artifact_path(run_dir)
        fields: dict[str, str] = {}
        if schema_path.exists():
            fields[RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH] = schema_path.relative_to(run_dir).as_posix()
        return fields

    def load_machine_schema(self, *, run_dir: Path) -> dict[str, Any] | None:
        schema_path = self._artifact_path(run_dir)
        if not schema_path.exists():
            return None
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to load materialized target output schema: %s", schema_path, exc_info=True)
            return None
        return payload if isinstance(payload, dict) else None

    def build_final_wrapper_schema(self, business_schema: dict[str, Any]) -> dict[str, Any]:
        return self._build_final_wrapper_schema(business_schema)

    def build_interactive_union_schema(self, final_schema: dict[str, Any]) -> dict[str, Any]:
        return self._build_interactive_union_schema(final_schema)

    def build_prompt_contract_markdown(
        self,
        *,
        final_schema: dict[str, Any],
        schema_relpath: str,
        execution_mode: str,
    ) -> str:
        pending_branch_note = None
        if self._normalize_execution_mode(execution_mode) == "interactive":
            pending_branch_note = build_interactive_pending_contract_note(
                include_final_example=False
            )
        return build_output_contract_details_markdown(
            final_schema,
            schema_artifact_relpath=schema_relpath,
            pending_branch_note=pending_branch_note,
        )

    def resolve_target_schema(
        self,
        *,
        skill: SkillManifest,
        execution_mode: str,
        run_dir: Path,
    ) -> dict[str, Any] | None:
        materialized = self.load_machine_schema(run_dir=run_dir)
        if isinstance(materialized, dict):
            return materialized
        business_schema = self._load_business_schema(skill)
        if business_schema is None:
            return None
        final_schema = self._build_final_wrapper_schema(business_schema)
        if self._normalize_execution_mode(execution_mode) == "interactive":
            return self._build_interactive_union_schema(final_schema)
        return final_schema

    def validate_target_output(
        self,
        *,
        schema: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> list[str]:
        if not isinstance(schema, dict):
            return ["Target output schema missing or unreadable"]
        try:
            jsonschema.validate(instance=payload, schema=schema)
            return []
        except jsonschema.ValidationError as exc:
            path = "/".join(str(item) for item in exc.path)
            path_suffix = f" (Path: {path})" if path else ""
            return [f"target output validation error: {exc.message}{path_suffix}"]
        except (jsonschema.SchemaError, TypeError, ValueError) as exc:
            return [f"target output validation failed: {str(exc)}"]

    def _load_business_schema(self, skill: SkillManifest) -> dict[str, Any] | None:
        resolution = resolve_schema_asset(skill, "output")
        schema_path = resolution.path
        if schema_path is None:
            return None
        payload = load_resolved_json(schema_path)
        if not isinstance(payload, dict):
            logger.warning("Output schema root is not an object: %s", schema_path)
            return None
        return payload

    def _build_final_wrapper_schema(self, business_schema: dict[str, Any]) -> dict[str, Any]:
        base_schema = deepcopy(business_schema)
        if base_schema.get("type") != "object":
            base_schema = {
                "type": "object",
                "properties": {"result": deepcopy(business_schema)},
                "required": ["result"],
                "additionalProperties": False,
            }
        properties_obj = base_schema.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        wrapped_properties: dict[str, Any] = {
            "__SKILL_DONE__": {
                "type": "boolean",
                "const": True,
                "description": "Completion signal. Must be true in the final payload.",
            }
        }
        for field_name, field_schema in properties.items():
            if not isinstance(field_name, str):
                continue
            wrapped_properties[field_name] = deepcopy(field_schema)
        base_schema["type"] = "object"
        base_schema["properties"] = wrapped_properties
        required_obj = base_schema.get("required")
        required = [item for item in required_obj if isinstance(item, str)] if isinstance(required_obj, list) else []
        base_schema["required"] = self._merge_required("__SKILL_DONE__", required)
        return base_schema

    def _build_interactive_union_schema(self, final_schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Skill Runner Interactive Output Contract",
            "oneOf": [
                deepcopy(final_schema),
                {
                    "type": "object",
                    "required": ["__SKILL_DONE__", "message", "ui_hints"],
                    "properties": {
                        "__SKILL_DONE__": {
                            "type": "boolean",
                            "const": False,
                            "description": "Pending-turn marker. Must be false when waiting for user input.",
                        },
                        "message": {
                            "type": "string",
                            "minLength": 1,
                            "description": "User-facing message for the pending interaction.",
                        },
                        "ui_hints": {
                            "type": "object",
                            "description": "Prompt/UI hint payload projected from ask_user capability vocabulary.",
                        },
                    },
                    "additionalProperties": True,
                },
            ],
        }

    def _append_request_input_audit_fields(
        self,
        *,
        run_dir: Path,
        fields: dict[str, Any],
    ) -> None:
        request_input_path = run_dir / ".audit" / "request_input.json"
        if not request_input_path.exists():
            return
        try:
            payload = json.loads(request_input_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            payload.update(fields)
            self._write_text_atomic(
                request_input_path,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "Failed to append target output schema paths into request_input.json",
                exc_info=True,
            )

    def _artifact_path(self, run_dir: Path) -> Path:
        return run_dir / TARGET_OUTPUT_SCHEMA_RELPATH

    def _normalize_execution_mode(self, execution_mode: str) -> str:
        mode = (execution_mode or "auto").strip().lower()
        return mode if mode in {"auto", "interactive"} else "auto"

    def _merge_required(self, first_field: str, required: list[str]) -> list[str]:
        merged = [first_field]
        for field_name in required:
            if field_name == first_field:
                continue
            merged.append(field_name)
        return merged

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        self._write_text_atomic(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def _write_text_atomic(self, path: Path, content: str) -> None:
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)


run_output_schema_service = RunOutputSchemaService()
