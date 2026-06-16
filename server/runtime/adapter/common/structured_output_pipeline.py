from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Mapping

import yaml  # type: ignore[import-untyped]

from server.config import config
from server.config_registry.registry import config_registry
from server.runtime.adapter.common.output_schema_cli import (
    RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH,
    TARGET_OUTPUT_SCHEMA_RELPATH,
)
from server.runtime.adapter.common.profile_loader import AdapterProfile, load_adapter_profile
from server.services.skill.skill_patch_output_schema import (
    build_schema_example_payload,
    build_codex_compatibility_note,
    build_codex_pending_branch_note,
    build_interactive_pending_contract_note,
    build_output_contract_details_markdown,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuredOutputArtifacts:
    canonical_schema_path: Path | None
    canonical_schema_relpath: str | None
    canonical_prompt_contract_markdown: str
    effective_schema_path: Path | None
    effective_schema_relpath: str | None
    effective_prompt_contract_markdown: str


@dataclass(frozen=True)
class _ObjectUnionInfo:
    keyword: str
    branches: tuple[dict[str, Any], ...]
    discriminator: str | None


class StructuredOutputPipeline:
    def resolve_artifacts(
        self,
        *,
        engine_name: str,
        run_dir: Path,
        options: Mapping[str, object],
        profile: AdapterProfile | None = None,
        canonical_prompt_contract_markdown: str | None = None,
    ) -> StructuredOutputArtifacts:
        normalized_engine = self._normalize_engine_name(engine_name)
        adapter_profile = profile or self._try_load_profile(normalized_engine)
        canonical_schema_path, canonical_schema_relpath = self._resolve_canonical_schema_path(
            run_dir=run_dir,
            options=options,
        )
        prompt_contract_markdown = (
            canonical_prompt_contract_markdown.strip()
            if isinstance(canonical_prompt_contract_markdown, str)
            and canonical_prompt_contract_markdown.strip()
            else self._build_prompt_contract_from_schema(
                schema_path=canonical_schema_path,
                schema_relpath=canonical_schema_relpath,
                execution_mode=self._resolve_execution_mode(options),
            )
        )
        effective_schema_path = canonical_schema_path
        effective_schema_relpath = canonical_schema_relpath
        effective_prompt_contract_markdown = prompt_contract_markdown

        if (
            adapter_profile is not None
            and
            adapter_profile.structured_output.compat_schema_strategy == "compat_translate"
            and normalized_engine == "codex"
            and canonical_schema_path is not None
        ):
            compat = self._materialize_codex_compat_artifacts(
                run_dir=run_dir,
                canonical_schema_path=canonical_schema_path,
                canonical_schema_relpath=canonical_schema_relpath,
                execution_mode=self._resolve_execution_mode(options),
            )
            effective_schema_path = compat.effective_schema_path
            effective_schema_relpath = compat.effective_schema_relpath
            if adapter_profile.structured_output.prompt_contract_strategy == "compat_summary":
                effective_prompt_contract_markdown = compat.effective_prompt_contract_markdown

        return StructuredOutputArtifacts(
            canonical_schema_path=canonical_schema_path,
            canonical_schema_relpath=canonical_schema_relpath,
            canonical_prompt_contract_markdown=prompt_contract_markdown,
            effective_schema_path=effective_schema_path,
            effective_schema_relpath=effective_schema_relpath,
            effective_prompt_contract_markdown=effective_prompt_contract_markdown,
        )

    def build_cli_schema_args(
        self,
        *,
        engine_name: str,
        run_dir: Path | None,
        options: Mapping[str, object],
        profile: AdapterProfile,
    ) -> list[str]:
        if not profile.command_features.inject_output_schema_cli or run_dir is None:
            return []
        artifacts = self.resolve_artifacts(
            engine_name=engine_name,
            run_dir=run_dir,
            options=options,
            profile=profile,
        )
        schema_path = artifacts.effective_schema_path
        schema_relpath = artifacts.effective_schema_relpath
        if schema_path is None:
            return []
        strategy = profile.structured_output.cli_schema_strategy
        if strategy == "path_schema_artifact":
            return ["--output-schema", schema_relpath] if isinstance(schema_relpath, str) else []
        if strategy == "inline_schema_object":
            payload = self._load_json_object(schema_path)
            if payload is None:
                return []
            return ["--json-schema", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
        return []

    def resolve_prompt_contract_markdown(
        self,
        *,
        engine_name: str,
        run_dir: Path,
        options: Mapping[str, object],
        profile: AdapterProfile | None = None,
        canonical_prompt_contract_markdown: str | None = None,
    ) -> str:
        artifacts = self.resolve_artifacts(
            engine_name=engine_name,
            run_dir=run_dir,
            options=options,
            profile=profile,
            canonical_prompt_contract_markdown=canonical_prompt_contract_markdown,
        )
        return artifacts.effective_prompt_contract_markdown

    def canonicalize_payload(
        self,
        *,
        engine_name: str,
        run_dir: Path,
        options: Mapping[str, object],
        payload: dict[str, Any],
        profile: AdapterProfile | None = None,
    ) -> dict[str, Any]:
        normalized_engine = self._normalize_engine_name(engine_name)
        adapter_profile = profile or self._try_load_profile(normalized_engine)
        if adapter_profile is None:
            return dict(payload)
        if adapter_profile.structured_output.payload_canonicalizer == "noop":
            return dict(payload)
        if (
            adapter_profile.structured_output.payload_canonicalizer == "payload_union_object_canonicalizer"
            and normalized_engine == "codex"
        ):
            artifacts = self.resolve_artifacts(
                engine_name=normalized_engine,
                run_dir=run_dir,
                options=options,
                profile=adapter_profile,
            )
            canonical_schema = (
                self._load_json_object(artifacts.canonical_schema_path)
                if artifacts.canonical_schema_path is not None
                else None
            )
            return self._canonicalize_codex_payload(payload=payload, canonical_schema=canonical_schema)
        return dict(payload)

    def _normalize_engine_name(self, engine_name: str) -> str:
        normalized = (engine_name or "").strip().lower()
        return normalized or "unknown"

    def _try_load_profile(self, engine_name: str) -> AdapterProfile | None:
        profile_path = (
            Path(config.SYSTEM.ROOT)
            / "server"
            / "engines"
            / engine_name
            / "adapter"
            / "adapter_profile.json"
        )
        try:
            return load_adapter_profile(engine_name, profile_path)
        except RuntimeError:
            return None

    def _resolve_execution_mode(self, options: Mapping[str, object]) -> str:
        raw = options.get("execution_mode")
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in {"auto", "interactive"}:
                return normalized
        return "auto"

    def _resolve_canonical_schema_path(
        self,
        *,
        run_dir: Path,
        options: Mapping[str, object],
    ) -> tuple[Path | None, str | None]:
        relpath = self._resolve_relpath(
            options.get(RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH),
            default_relpath=TARGET_OUTPUT_SCHEMA_RELPATH,
            run_dir=run_dir,
        )
        if relpath is None:
            return None, None
        return run_dir / relpath, relpath

    def _resolve_relpath(
        self,
        raw_value: object,
        *,
        default_relpath: str,
        run_dir: Path,
    ) -> str | None:
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()
        default_path = run_dir / default_relpath
        return default_relpath if default_path.exists() else None

    def _build_prompt_contract_from_schema(
        self,
        *,
        schema_path: Path | None,
        schema_relpath: str | None,
        execution_mode: str,
    ) -> str:
        if schema_path is None or not isinstance(schema_relpath, str):
            return ""
        schema = self._load_json_object(schema_path)
        if not isinstance(schema, dict):
            return ""
        final_branch, pending_branch = self._extract_canonical_branches(schema)
        pending_branch_note = None
        if execution_mode == "interactive" and pending_branch is not None:
            pending_branch_note = self._build_interactive_prompt_contract_note()
        return build_output_contract_details_markdown(
            final_branch,
            schema_artifact_relpath=schema_relpath,
            pending_branch_note=pending_branch_note,
        )

    def _load_json_object(self, path: Path | None) -> dict[str, Any] | None:
        if path is None or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to load structured output schema: %s", path, exc_info=True)
            return None
        return payload if isinstance(payload, dict) else None

    def _materialize_codex_compat_artifacts(
        self,
        *,
        run_dir: Path,
        canonical_schema_path: Path,
        canonical_schema_relpath: str | None,
        execution_mode: str,
    ) -> StructuredOutputArtifacts:
        canonical_schema = self._load_json_object(canonical_schema_path)
        if canonical_schema is None:
            return StructuredOutputArtifacts(
                canonical_schema_path=canonical_schema_path,
                canonical_schema_relpath=canonical_schema_relpath,
                canonical_prompt_contract_markdown="",
                effective_schema_path=canonical_schema_path,
                effective_schema_relpath=canonical_schema_relpath,
                effective_prompt_contract_markdown="",
            )

        compat_schema = self._build_codex_compat_schema(
            canonical_schema=canonical_schema,
            execution_mode=execution_mode,
        )
        compat_schema_relpath = ".audit/contracts/target_output_schema.codex_compatible.json"
        compat_schema_path = run_dir / compat_schema_relpath
        compat_schema_path.parent.mkdir(parents=True, exist_ok=True)
        compat_prompt_contract_markdown = self._build_codex_compat_prompt_contract_markdown(
            compat_schema=compat_schema,
            canonical_schema=canonical_schema,
            compat_schema_relpath=compat_schema_relpath,
            execution_mode=execution_mode,
        )
        self._write_json_atomic(compat_schema_path, compat_schema)
        return StructuredOutputArtifacts(
            canonical_schema_path=canonical_schema_path,
            canonical_schema_relpath=canonical_schema_relpath,
            canonical_prompt_contract_markdown="",
            effective_schema_path=compat_schema_path,
            effective_schema_relpath=compat_schema_relpath,
            effective_prompt_contract_markdown=compat_prompt_contract_markdown,
        )

    def _build_codex_compat_schema(
        self,
        *,
        canonical_schema: dict[str, Any],
        execution_mode: str,
    ) -> dict[str, Any]:
        final_branch, pending_branch = self._extract_canonical_branches(canonical_schema)
        final_properties = self._translate_object_properties(final_branch)
        if execution_mode == "interactive" and pending_branch is not None:
            union_properties: dict[str, Any] = {
                "__SKILL_DONE__": {
                    "type": "boolean",
                    "description": "True when the task is complete. False when more user input is required.",
                }
            }
            for field_name, field_schema in final_properties.items():
                if field_name == "__SKILL_DONE__":
                    continue
                union_properties[field_name] = self._nullable_schema(field_schema)
            pending_properties = self._build_pending_compat_properties(pending_branch)
            for field_name, field_schema in pending_properties.items():
                if field_name == "__SKILL_DONE__":
                    continue
                union_properties[field_name] = self._nullable_schema(field_schema)
            return {
                "type": "object",
                "properties": union_properties,
                "required": list(union_properties.keys()),
                "additionalProperties": False,
            }
        return {
            "type": "object",
            "properties": final_properties,
            "required": list(final_properties.keys()),
            "additionalProperties": False,
        }

    def _extract_canonical_branches(
        self,
        canonical_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        branches_obj = canonical_schema.get("oneOf")
        if not isinstance(branches_obj, list):
            return canonical_schema, None
        final_branch: dict[str, Any] | None = None
        pending_branch: dict[str, Any] | None = None
        for branch in branches_obj:
            if not isinstance(branch, dict):
                continue
            marker_const = (
                branch.get("properties", {})
                .get("__SKILL_DONE__", {})
                .get("const")
            )
            if marker_const is True:
                final_branch = branch
            elif marker_const is False:
                pending_branch = branch
        if final_branch is not None and pending_branch is not None:
            return final_branch, pending_branch
        return canonical_schema, None

    def _translate_object_properties(self, schema: dict[str, Any]) -> dict[str, Any]:
        object_union = self._extract_object_union_info(schema)
        if object_union is not None and object_union.discriminator is not None:
            return self._translate_object_union_properties(
                schema,
                object_union=object_union,
            )
        properties_obj = schema.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        required_obj = schema.get("required")
        required_set = {
            item for item in required_obj
            if isinstance(item, str)
        } if isinstance(required_obj, list) else set()
        translated: dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            if not isinstance(field_name, str):
                continue
            translated_schema = self._translate_schema(field_schema if isinstance(field_schema, dict) else {})
            if field_name == "__SKILL_DONE__":
                translated[field_name] = {
                    "type": "boolean",
                    "description": str(translated_schema.get("description") or "Completion marker."),
                }
                continue
            if field_name not in required_set:
                translated_schema = self._nullable_schema(translated_schema)
            translated[field_name] = translated_schema
        if "__SKILL_DONE__" not in translated:
            translated["__SKILL_DONE__"] = {
                "type": "boolean",
                "description": "Completion marker.",
            }
        return translated

    def _extract_object_union_info(
        self,
        schema: dict[str, Any],
    ) -> _ObjectUnionInfo | None:
        if schema.get("type") != "object":
            return None
        for keyword in ("oneOf", "anyOf"):
            branches_obj = schema.get(keyword)
            if not isinstance(branches_obj, list) or len(branches_obj) < 2:
                continue
            branches = tuple(
                branch
                for branch in branches_obj
                if isinstance(branch, dict)
                and (
                    branch.get("type") == "object"
                    or isinstance(branch.get("properties"), dict)
                )
            )
            if len(branches) < 2:
                continue
            return _ObjectUnionInfo(
                keyword=keyword,
                branches=branches,
                discriminator=self._detect_const_discriminator(branches),
            )
        return None

    def _detect_const_discriminator(
        self,
        branches: tuple[dict[str, Any], ...],
    ) -> str | None:
        if len(branches) < 2:
            return None
        first_properties_obj = branches[0].get("properties")
        first_properties = first_properties_obj if isinstance(first_properties_obj, dict) else {}
        candidate_names = [
            field_name
            for field_name in first_properties
            if isinstance(field_name, str) and field_name != "__SKILL_DONE__"
        ]
        valid_candidates: list[str] = []
        for field_name in candidate_names:
            const_values: list[Any] = []
            for branch in branches:
                properties_obj = branch.get("properties")
                properties = properties_obj if isinstance(properties_obj, dict) else {}
                field_schema = properties.get(field_name)
                if not isinstance(field_schema, dict) or "const" not in field_schema:
                    break
                const_values.append(field_schema.get("const"))
            else:
                if len(const_values) == len(branches) and len({json.dumps(value, sort_keys=True) for value in const_values}) == len(branches):
                    valid_candidates.append(field_name)
        if "kind" in valid_candidates:
            return "kind"
        return valid_candidates[0] if valid_candidates else None

    def _translate_object_union_properties(
        self,
        schema: dict[str, Any],
        *,
        object_union: _ObjectUnionInfo,
    ) -> dict[str, Any]:
        root_without_union = {
            key: value
            for key, value in schema.items()
            if key not in {"oneOf", "anyOf"}
        }
        translated = self._translate_object_properties(root_without_union)
        discriminator = object_union.discriminator
        branch_field_order: list[str] = []
        branch_field_schemas: dict[str, list[dict[str, Any]]] = {}
        branch_field_required: dict[str, list[bool]] = {}
        discriminator_values: list[Any] = []

        for branch in object_union.branches:
            properties_obj = branch.get("properties")
            properties = properties_obj if isinstance(properties_obj, dict) else {}
            required_obj = branch.get("required")
            required = {
                item for item in required_obj
                if isinstance(item, str)
            } if isinstance(required_obj, list) else set()
            discriminator_schema = properties.get(discriminator)
            if isinstance(discriminator_schema, dict):
                discriminator_values.append(discriminator_schema.get("const"))
            for field_name, field_schema in properties.items():
                if not isinstance(field_name, str):
                    continue
                if field_name not in branch_field_order:
                    branch_field_order.append(field_name)
                schema_dict = field_schema if isinstance(field_schema, dict) else {}
                branch_field_schemas.setdefault(field_name, []).append(schema_dict)
                branch_field_required.setdefault(field_name, []).append(field_name in required)

        for field_name in branch_field_order:
            if field_name == "__SKILL_DONE__":
                translated[field_name] = {
                    "type": "boolean",
                    "description": "Completion marker.",
                }
                continue
            if field_name == discriminator:
                translated[field_name] = self._translate_discriminator_schema(
                    field_name=field_name,
                    values=discriminator_values,
                    schemas=branch_field_schemas.get(field_name, []),
                )
                continue

            translated_schema = self._merge_translated_branch_field_schemas(
                branch_field_schemas.get(field_name, [])
            )
            field_presence_count = len(branch_field_schemas.get(field_name, []))
            required_flags = branch_field_required.get(field_name, [])
            if field_presence_count < len(object_union.branches) or not all(required_flags):
                translated_schema = self._nullable_schema(translated_schema)
            translated[field_name] = translated_schema

        if "__SKILL_DONE__" not in translated:
            translated["__SKILL_DONE__"] = {
                "type": "boolean",
                "description": "Completion marker.",
            }
        return translated

    def _translate_discriminator_schema(
        self,
        *,
        field_name: str,
        values: list[Any],
        schemas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        translated = self._merge_translated_branch_field_schemas(schemas)
        translated.pop("const", None)
        translated["enum"] = values
        if "type" not in translated:
            translated["type"] = "string"
        translated["description"] = str(
            translated.get("description") or f"Discriminator selecting the {field_name} output branch."
        )
        return translated

    def _merge_translated_branch_field_schemas(
        self,
        schemas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        translated_options = [
            self._translate_schema(schema)
            for schema in schemas
            if isinstance(schema, dict)
        ]
        translated_options = [schema for schema in translated_options if schema]
        if not translated_options:
            return {"type": "string", "description": "String value."}
        first = translated_options[0]
        if all(option == first for option in translated_options):
            return deepcopy(first)
        if all(option.get("type") == "string" and isinstance(option.get("enum"), list) for option in translated_options):
            enum_values: list[Any] = []
            for option in translated_options:
                for value in option.get("enum", []):
                    if value not in enum_values:
                        enum_values.append(value)
            merged = deepcopy(first)
            merged["enum"] = enum_values
            return merged
        return {"anyOf": [deepcopy(option) for option in translated_options]}

    def _build_pending_compat_properties(self, pending_schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "__SKILL_DONE__": {
                "type": "boolean",
                "description": "False when more user input is required.",
            },
            "message": {
                "type": "string",
                "description": str(
                    pending_schema.get("properties", {})
                    .get("message", {})
                    .get("description")
                    or "User-facing message for the pending interaction."
                ),
            },
            "ui_hints": self._build_ui_hints_schema(),
        }

    def _build_ui_hints_schema(self) -> dict[str, Any]:
        contract = self._load_ui_hints_contract()
        option_item = {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Option label shown to the user."},
                "value": self._nullable_schema({"type": "string", "description": "Option value."}),
            },
            "required": ["label", "value"],
            "additionalProperties": False,
        }
        file_item = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Logical file field name."},
                "required": {"type": "boolean", "description": "Whether the file is required."},
                "hint": self._nullable_schema({"type": "string", "description": "Extra upload hint."}),
                "accept": self._nullable_schema({"type": "string", "description": "Accepted file types."}),
            },
            "required": ["name", "required", "hint", "accept"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "kind": self._nullable_schema(
                    {
                        "type": "string",
                        "enum": list(contract["kinds"]),
                        "description": "UI interaction kind.",
                    }
                ),
                "prompt": self._nullable_schema(
                    {"type": "string", "description": "Optional UI prompt text."}
                ),
                "hint": self._nullable_schema(
                    {"type": "string", "description": "Optional UI hint text."}
                ),
                "options": self._nullable_schema(
                    {
                        "type": "array",
                        "items": option_item,
                        "description": "Options for choose_one interactions.",
                    }
                ),
                "files": self._nullable_schema(
                    {
                        "type": "array",
                        "items": file_item,
                        "description": "File upload descriptors.",
                    }
                ),
            },
            "required": ["kind", "prompt", "hint", "options", "files"],
            "additionalProperties": False,
        }

    def _translate_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        raw_type = schema.get("type")
        if schema.get("x-type") in {"artifact", "file"}:
            return {
                "type": "string",
                "description": str(schema.get("description") or "Artifact output path."),
            }
        if isinstance(raw_type, list):
            if "null" in raw_type and len(raw_type) > 1:
                non_null = [item for item in raw_type if item != "null"]
                inner = self._translate_schema({**schema, "type": non_null[0] if len(non_null) == 1 else non_null})
                return self._nullable_schema(inner)
            if len(raw_type) == 1 and isinstance(raw_type[0], str):
                return self._translate_schema({**schema, "type": raw_type[0]})
        if isinstance(raw_type, str):
            if raw_type in {"string", "number", "integer", "boolean", "null"}:
                return self._translate_scalar_schema(schema)
            if raw_type == "array":
                return self._translate_array_schema(schema)
            if raw_type == "object":
                return self._translate_object_schema(schema)
        combo = schema.get("anyOf") or schema.get("oneOf")
        if isinstance(combo, list):
            translated_options = [
                self._translate_schema(item)
                for item in combo
                if isinstance(item, dict)
            ]
            translated_options = [item for item in translated_options if item]
            if translated_options:
                return {
                    "anyOf": translated_options,
                    **(
                        {"description": str(schema.get("description"))}
                        if isinstance(schema.get("description"), str) and str(schema.get("description")).strip()
                        else {}
                    ),
                }
        return {
            "type": "string",
            "description": str(schema.get("description") or "String value."),
        }

    def _translate_scalar_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        translated: dict[str, Any] = {"type": schema.get("type")}
        for key in (
            "description",
            "enum",
            "pattern",
            "format",
            "multipleOf",
            "maximum",
            "exclusiveMaximum",
            "minimum",
            "exclusiveMinimum",
        ):
            value = schema.get(key)
            if value is not None:
                translated[key] = deepcopy(value)
        const_value = schema.get("const")
        if const_value is not None:
            translated["enum"] = [const_value]
        return translated

    def _translate_array_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        items_obj = schema.get("items")
        translated: dict[str, Any] = {
            "type": "array",
            "items": self._translate_schema(items_obj if isinstance(items_obj, dict) else {}),
        }
        for key in ("description", "minItems", "maxItems"):
            value = schema.get(key)
            if value is not None:
                translated[key] = deepcopy(value)
        return translated

    def _translate_object_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        properties_obj = schema.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        required_obj = schema.get("required")
        required_set = {
            item for item in required_obj
            if isinstance(item, str)
        } if isinstance(required_obj, list) else set()
        translated_props: dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            if not isinstance(field_name, str):
                continue
            translated_field = self._translate_schema(field_schema if isinstance(field_schema, dict) else {})
            if field_name not in required_set:
                translated_field = self._nullable_schema(translated_field)
            translated_props[field_name] = translated_field
        return {
            "type": "object",
            "properties": translated_props,
            "required": list(translated_props.keys()),
            "additionalProperties": False,
            **(
                {"description": str(schema.get("description"))}
                if isinstance(schema.get("description"), str) and str(schema.get("description")).strip()
                else {}
            ),
        }

    def _nullable_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        if not schema:
            return {"anyOf": [{"type": "null"}, {"type": "string"}]}
        if schema.get("type") == "null":
            return dict(schema)
        combo = schema.get("anyOf")
        if isinstance(combo, list) and any(isinstance(item, dict) and item.get("type") == "null" for item in combo):
            return dict(schema)
        return {
            "anyOf": [
                deepcopy(schema),
                {"type": "null"},
            ]
        }

    def _build_codex_compat_prompt_contract_markdown(
        self,
        *,
        compat_schema: dict[str, Any],
        canonical_schema: dict[str, Any],
        compat_schema_relpath: str,
        execution_mode: str,
    ) -> str:
        canonical_final_branch, _pending_branch = self._extract_canonical_branches(canonical_schema)
        final_result_fields = [
            field_name
            for field_name in compat_schema.get("properties", {})
            if isinstance(field_name, str) and field_name not in {"__SKILL_DONE__", "message", "ui_hints"}
        ]
        pending_branch_note = (
            build_codex_pending_branch_note(final_result_fields=final_result_fields)
            if execution_mode == "interactive"
            else None
        )
        example_payload = self._build_codex_final_example_payload(
            compat_schema=compat_schema,
            canonical_final_branch=canonical_final_branch,
            execution_mode=execution_mode,
        )
        return build_output_contract_details_markdown(
            compat_schema,
            schema_artifact_relpath=compat_schema_relpath,
            pending_branch_note=pending_branch_note,
            compatibility_note=build_codex_compatibility_note(execution_mode=execution_mode),
            example_payload=example_payload,
        )

    def _build_interactive_prompt_contract_note(self) -> str:
        return build_interactive_pending_contract_note(include_final_example=False)

    def _build_codex_final_example_payload(
        self,
        *,
        compat_schema: dict[str, Any],
        canonical_final_branch: dict[str, Any],
        execution_mode: str,
    ) -> dict[str, Any]:
        example_schema = self._codex_example_schema(canonical_final_branch)
        example = build_schema_example_payload(example_schema)
        discriminator_example = self._codex_example_discriminator_value(canonical_final_branch)
        if discriminator_example is not None:
            field_name, value = discriminator_example
            example[field_name] = value
        compat_properties_obj = compat_schema.get("properties")
        compat_properties = compat_properties_obj if isinstance(compat_properties_obj, dict) else {}
        for field_name in compat_properties:
            if not isinstance(field_name, str):
                continue
            if field_name in example:
                continue
            if field_name == "message":
                example[field_name] = None
                continue
            if field_name == "ui_hints":
                example[field_name] = None
                continue
            example[field_name] = None
        if execution_mode == "interactive":
            example["message"] = None
            example["ui_hints"] = None
        return example

    def _codex_example_schema(self, canonical_final_branch: dict[str, Any]) -> dict[str, Any]:
        object_union = self._extract_object_union_info(canonical_final_branch)
        if object_union is None or object_union.discriminator is None:
            return canonical_final_branch
        branch = object_union.branches[0]
        merged = {
            key: deepcopy(value)
            for key, value in canonical_final_branch.items()
            if key not in {"oneOf", "anyOf"}
        }
        root_properties_obj = merged.get("properties")
        root_properties = root_properties_obj if isinstance(root_properties_obj, dict) else {}
        branch_properties_obj = branch.get("properties")
        branch_properties = branch_properties_obj if isinstance(branch_properties_obj, dict) else {}
        merged["properties"] = {
            **deepcopy(root_properties),
            **deepcopy(branch_properties),
        }
        for field_schema in merged["properties"].values():
            if isinstance(field_schema, dict) and "const" in field_schema and "type" not in field_schema:
                const_value = field_schema.get("const")
                inferred_type = self._json_type_name(const_value)
                if inferred_type is not None:
                    field_schema["type"] = inferred_type
        root_required_obj = merged.get("required")
        root_required = [
            item for item in root_required_obj
            if isinstance(item, str)
        ] if isinstance(root_required_obj, list) else []
        branch_required_obj = branch.get("required")
        branch_required = [
            item for item in branch_required_obj
            if isinstance(item, str)
        ] if isinstance(branch_required_obj, list) else []
        merged["required"] = list(dict.fromkeys([*root_required, *branch_required]))
        return merged

    def _codex_example_discriminator_value(
        self,
        canonical_final_branch: dict[str, Any],
    ) -> tuple[str, Any] | None:
        object_union = self._extract_object_union_info(canonical_final_branch)
        if object_union is None or object_union.discriminator is None:
            return None
        branch = object_union.branches[0]
        properties_obj = branch.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        discriminator_schema = properties.get(object_union.discriminator)
        if not isinstance(discriminator_schema, dict) or "const" not in discriminator_schema:
            return None
        return object_union.discriminator, discriminator_schema.get("const")

    def _json_type_name(self, value: Any) -> str | None:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if value is None:
            return "null"
        return None

    def _load_ui_hints_contract(self) -> dict[str, Any]:
        fallback = {
            "kinds": ("open_text", "choose_one", "confirm", "upload_files"),
        }
        contract_path = next((path for path in config_registry.ask_user_schema_paths() if path.exists()), None)
        if contract_path is None:
            return fallback
        try:
            payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            logger.warning("Failed to load ask_user schema for structured output compatibility", exc_info=True)
            return fallback
        if not isinstance(payload, dict):
            return fallback
        properties_obj = payload.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        kind_obj = properties.get("kind")
        kind_enum = kind_obj.get("enum") if isinstance(kind_obj, dict) else None
        if isinstance(kind_enum, list) and kind_enum:
            kinds = tuple(str(item) for item in kind_enum if isinstance(item, str) and item.strip())
            if kinds:
                return {"kinds": kinds}
        return fallback

    def _canonicalize_codex_payload(
        self,
        *,
        payload: dict[str, Any],
        canonical_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        marker = payload.get("__SKILL_DONE__")
        final_schema, pending_schema = self._extract_canonical_branches(canonical_schema or {})
        if marker is False and pending_schema is not None:
            canonical_pending: dict[str, Any] = {"__SKILL_DONE__": False}
            if isinstance(payload.get("message"), str):
                canonical_pending["message"] = payload["message"]
            ui_hints_obj = payload.get("ui_hints")
            if isinstance(ui_hints_obj, dict):
                canonical_pending["ui_hints"] = self._strip_nulls(ui_hints_obj)
            return canonical_pending
        canonical_final = self._project_payload_against_schema(payload, final_schema)
        if "__SKILL_DONE__" in payload:
            canonical_final["__SKILL_DONE__"] = bool(payload.get("__SKILL_DONE__"))
        return canonical_final

    def _project_payload_against_schema(
        self,
        payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        selected_union_branch = self._select_object_union_branch(
            payload=payload,
            schema=schema,
        )
        if selected_union_branch is not None:
            root_schema = {
                key: value
                for key, value in schema.items()
                if key not in {"oneOf", "anyOf"}
            }
            projected = self._project_payload_against_schema(payload, root_schema)
            projected.update(
                self._project_payload_against_schema(payload, selected_union_branch)
            )
            return projected

        properties_obj = schema.get("properties")
        properties = properties_obj if isinstance(properties_obj, dict) else {}
        projected: dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            if not isinstance(field_name, str) or field_name not in payload:
                continue
            value = payload[field_name]
            schema_dict = field_schema if isinstance(field_schema, dict) else {}
            if value is None and not self._schema_allows_null(schema_dict):
                continue
            if isinstance(value, dict):
                projected[field_name] = self._project_payload_against_schema(value, schema_dict)
                continue
            if isinstance(value, list):
                projected[field_name] = self._project_list_against_schema(value, schema_dict)
                continue
            projected[field_name] = value
        return projected

    def _project_list_against_schema(
        self,
        values: list[Any],
        schema: dict[str, Any],
    ) -> list[Any]:
        items_obj = schema.get("items")
        item_schema = items_obj if isinstance(items_obj, dict) else {}
        projected: list[Any] = []
        for item in values:
            if item is None and not self._schema_allows_null(item_schema):
                continue
            if isinstance(item, dict):
                projected.append(self._project_payload_against_schema(item, item_schema))
            elif isinstance(item, list):
                projected.append(self._project_list_against_schema(item, item_schema))
            else:
                projected.append(item)
        return projected

    def _select_object_union_branch(
        self,
        *,
        payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any] | None:
        object_union = self._extract_object_union_info(schema)
        if object_union is None or object_union.discriminator is None:
            return None
        discriminator_value = payload.get(object_union.discriminator)
        for branch in object_union.branches:
            properties_obj = branch.get("properties")
            properties = properties_obj if isinstance(properties_obj, dict) else {}
            discriminator_schema = properties.get(object_union.discriminator)
            if (
                isinstance(discriminator_schema, dict)
                and discriminator_schema.get("const") == discriminator_value
            ):
                return branch
        return None

    def _schema_allows_null(self, schema: dict[str, Any]) -> bool:
        raw_type = schema.get("type")
        if raw_type == "null":
            return True
        if isinstance(raw_type, list) and "null" in raw_type:
            return True
        combo = schema.get("anyOf") or schema.get("oneOf")
        if isinstance(combo, list):
            return any(isinstance(item, dict) and self._schema_allows_null(item) for item in combo)
        return False

    def _strip_nulls(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: stripped
                for key, stripped in (
                    (key, self._strip_nulls(item))
                    for key, item in value.items()
                    if isinstance(key, str)
                )
                if stripped is not None
            }
        if isinstance(value, list):
            return [item for item in (self._strip_nulls(item) for item in value) if item is not None]
        return value

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)


structured_output_pipeline = StructuredOutputPipeline()
