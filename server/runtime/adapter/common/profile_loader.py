from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

import jsonschema  # type: ignore[import-untyped]
from server.config_registry import keys
from server.config_registry.registry import config_registry


SCHEMA_PATHS = config_registry.adapter_profile_schema_paths()


PromptParamsJsonSource = Literal["none", "input_data", "combined_input_parameter"]
PromptSource = Literal["none", "parameter.prompt"]
SessionStrategy = Literal["first_json_line", "json_recursive_key", "json_lines_scan", "regex_extract"]
SessionTextFinder = Literal["find_session_id_in_text"]
SessionJsonLineFinder = Literal["find_session_id"]
ModelCatalogMode = Literal["manifest", "runtime_probe"]
CredentialPolicyMode = Literal["all_of_sources", "any_of_sources"]
SettingsValidator = Literal["iflow_oauth_settings"]
BootstrapFormat = Literal["json", "text"]
NormalizeStrategy = Literal["iflow_settings_v1"]
ImportValidatorName = Literal[
    "json_object",
    "codex_auth_json",
    "gemini_google_accounts_json",
    "gemini_oauth_creds_json",
    "iflow_accounts_json",
    "iflow_oauth_creds_json",
    "opencode_auth_json",
    "opencode_antigravity_accounts_json",
]


@dataclass(frozen=True)
class PromptBuilderProfile:
    engine_key: str
    default_template_path: str | None
    fallback_inline: str
    merge_input_if_no_parameter_schema: bool
    params_json_source: PromptParamsJsonSource
    main_prompt_source: PromptSource
    main_prompt_default_template: str
    include_input_file_name: bool
    include_skill_dir: bool


@dataclass(frozen=True)
class SessionCodecProfile:
    strategy: SessionStrategy
    error_message: str
    error_prefix: str | None
    required_type: str | None
    id_field: str | None
    recursive_key: str | None
    fallback_text_finder: SessionTextFinder | None
    json_lines_finder: SessionJsonLineFinder | None
    regex_pattern: str | None


@dataclass(frozen=True)
class AttemptWorkspaceProfile:
    workspace_subdir: str
    skills_subdir: str
    use_config_parent_as_workspace: bool
    unknown_fallback: bool


@dataclass(frozen=True)
class ConfigAssetsProfile:
    bootstrap_path: str
    default_path: str
    enforced_path: str
    settings_schema_path: str | None
    skill_defaults_path: str | None


@dataclass(frozen=True)
class ModelCatalogProfile:
    mode: ModelCatalogMode
    manifest_path: str | None
    models_root: str | None
    seed_path: str | None


@dataclass(frozen=True)
class CredentialImportProfile:
    source: str
    target_relpath: str
    import_validator: ImportValidatorName | None
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CredentialPolicyProfile:
    mode: CredentialPolicyMode
    sources: tuple[str, ...]
    settings_validator: SettingsValidator | None


@dataclass(frozen=True)
class ResumeProbeProfile:
    help_hints: tuple[str, ...]
    dynamic_args: tuple[str, ...]


@dataclass(frozen=True)
class LayoutProfile:
    extra_dirs: tuple[str, ...]
    bootstrap_target_relpath: str
    bootstrap_format: BootstrapFormat
    normalize_strategy: NormalizeStrategy | None


@dataclass(frozen=True)
class CliManagementProfile:
    package: str
    binary_candidates: tuple[str, ...]
    credential_imports: tuple[CredentialImportProfile, ...]
    credential_policy: CredentialPolicyProfile
    resume_probe: ResumeProbeProfile
    layout: LayoutProfile


@dataclass(frozen=True)
class ParserAuthPatternsProfile:
    rules: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ParserStructuredExtractProfile:
    event_type: str
    session_id_key: str
    response_key: str
    summary_max_chars: int


@dataclass(frozen=True)
class AdapterProfile:
    engine: str
    profile_path: Path
    prompt_builder: PromptBuilderProfile
    session_codec: SessionCodecProfile
    attempt_workspace: AttemptWorkspaceProfile
    config_assets: ConfigAssetsProfile
    model_catalog: ModelCatalogProfile
    cli_management: CliManagementProfile
    parser_auth_patterns: ParserAuthPatternsProfile
    parser_structured_extract: ParserStructuredExtractProfile | None

    def _resolve_profile_relative_path(self, path_value: str | None) -> Path | None:
        if not isinstance(path_value, str) or not path_value.strip():
            return None
        candidate = Path(path_value.strip())
        if not candidate.is_absolute():
            candidate = (self.profile_path.parent / candidate).resolve()
        return candidate

    def resolve_template_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.prompt_builder.default_template_path)

    def resolve_bootstrap_path(self) -> Path:
        resolved = self._resolve_profile_relative_path(self.config_assets.bootstrap_path)
        if resolved is None:
            raise RuntimeError(f"adapter profile missing bootstrap path: {self.profile_path}")
        return resolved

    def resolve_default_config_path(self) -> Path:
        resolved = self._resolve_profile_relative_path(self.config_assets.default_path)
        if resolved is None:
            raise RuntimeError(f"adapter profile missing default config path: {self.profile_path}")
        return resolved

    def resolve_enforced_config_path(self) -> Path:
        resolved = self._resolve_profile_relative_path(self.config_assets.enforced_path)
        if resolved is None:
            raise RuntimeError(f"adapter profile missing enforced config path: {self.profile_path}")
        return resolved

    def resolve_settings_schema_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.config_assets.settings_schema_path)

    def resolve_skill_defaults_path(self, skill_path: Path | None) -> Path | None:
        raw = self.config_assets.skill_defaults_path
        if not isinstance(raw, str) or not raw.strip() or skill_path is None:
            return None
        candidate = Path(raw.strip())
        if candidate.is_absolute():
            return candidate
        return skill_path / candidate

    def resolve_manifest_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.model_catalog.manifest_path)

    def resolve_models_root(self) -> Path | None:
        explicit = self._resolve_profile_relative_path(self.model_catalog.models_root)
        if explicit is not None:
            return explicit
        manifest_path = self.resolve_manifest_path()
        if manifest_path is not None:
            return manifest_path.parent
        return None

    def resolve_seed_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.model_catalog.seed_path)

    def skills_root_from(self, run_dir: Path, config_path: Path) -> Path:
        workspace = (
            config_path.parent
            if self.attempt_workspace.use_config_parent_as_workspace
            else run_dir / self.attempt_workspace.workspace_subdir
        )
        return workspace / self.attempt_workspace.skills_subdir


def _load_schema() -> dict[str, Any]:
    schema_path = next((path for path in SCHEMA_PATHS if path.exists()), None)
    if schema_path is None:
        joined = ", ".join(str(path) for path in SCHEMA_PATHS)
        raise RuntimeError(f"Adapter profile schema not found. tried: {joined}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _validate_resolved_path(
    *,
    profile_path: Path,
    label: str,
    raw_value: str | None,
    must_exist: bool = True,
) -> None:
    if raw_value is None:
        return
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise RuntimeError(f"Adapter profile invalid {label}: empty path ({profile_path})")
    candidate = Path(raw_value.strip())
    if not candidate.is_absolute():
        candidate = (profile_path.parent / candidate).resolve()
    if must_exist and not candidate.exists():
        raise RuntimeError(f"Adapter profile invalid {label}: path not found ({candidate})")


@lru_cache(maxsize=16)
def _load_adapter_profile_cached(engine: str, profile_path_str: str) -> AdapterProfile:
    profile_path = Path(profile_path_str)
    if not profile_path.exists():
        raise RuntimeError(f"Adapter profile not found for {engine}: {profile_path}")

    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    schema = _load_schema()
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"Adapter profile validation failed for {engine} ({profile_path}): {exc.message}"
        ) from exc

    payload_engine = payload.get("engine")
    if payload_engine != engine:
        raise RuntimeError(
            f"Adapter profile engine mismatch: expected '{engine}', got '{payload_engine}' ({profile_path})"
        )

    prompt_raw = payload["prompt_builder"]
    session_raw = payload["session_codec"]
    workspace_raw = payload["attempt_workspace"]
    config_assets_raw = payload["config_assets"]
    model_catalog_raw = payload["model_catalog"]
    cli_management_raw = payload["cli_management"]
    parser_auth_patterns_raw = payload["parser_auth_patterns"]
    parser_structured_extract_raw = payload.get("parser_structured_extract")

    _validate_resolved_path(
        profile_path=profile_path,
        label="config_assets.bootstrap_path",
        raw_value=config_assets_raw.get("bootstrap_path"),
    )
    _validate_resolved_path(
        profile_path=profile_path,
        label="config_assets.default_path",
        raw_value=config_assets_raw.get("default_path"),
    )
    _validate_resolved_path(
        profile_path=profile_path,
        label="config_assets.enforced_path",
        raw_value=config_assets_raw.get("enforced_path"),
    )
    _validate_resolved_path(
        profile_path=profile_path,
        label="config_assets.settings_schema_path",
        raw_value=config_assets_raw.get("settings_schema_path"),
    )
    skill_defaults_raw = config_assets_raw.get("skill_defaults_path")
    if skill_defaults_raw is not None and (
        not isinstance(skill_defaults_raw, str) or not skill_defaults_raw.strip()
    ):
        raise RuntimeError(
            f"Adapter profile invalid config_assets.skill_defaults_path: empty path ({profile_path})"
        )
    _validate_resolved_path(
        profile_path=profile_path,
        label="model_catalog.manifest_path",
        raw_value=model_catalog_raw.get("manifest_path"),
    )
    _validate_resolved_path(
        profile_path=profile_path,
        label="model_catalog.models_root",
        raw_value=model_catalog_raw.get("models_root"),
    )
    _validate_resolved_path(
        profile_path=profile_path,
        label="model_catalog.seed_path",
        raw_value=model_catalog_raw.get("seed_path"),
    )
    for index, item in enumerate(cli_management_raw.get("credential_imports", [])):
        if not isinstance(item, dict):
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}]: expected object ({profile_path})"
            )
        source_raw = item.get("source")
        target_raw = item.get("target_relpath")
        if not isinstance(source_raw, str) or not source_raw.strip():
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}].source: empty ({profile_path})"
            )
        if not isinstance(target_raw, str) or not target_raw.strip():
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}].target_relpath: empty ({profile_path})"
            )
        target_path = Path(target_raw.strip())
        if target_path.is_absolute():
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}].target_relpath: must be relative ({profile_path})"
            )
        import_validator_raw = item.get("import_validator")
        if import_validator_raw is not None and (
            not isinstance(import_validator_raw, str) or not import_validator_raw.strip()
        ):
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}].import_validator: invalid ({profile_path})"
            )
        aliases_raw = item.get("aliases", [])
        if aliases_raw is not None and not isinstance(aliases_raw, list):
            raise RuntimeError(
                f"Adapter profile invalid cli_management.credential_imports[{index}].aliases: expected array ({profile_path})"
            )
        for alias_index, alias_value in enumerate(aliases_raw or []):
            if not isinstance(alias_value, str) or not alias_value.strip():
                raise RuntimeError(
                    f"Adapter profile invalid cli_management.credential_imports[{index}].aliases[{alias_index}]: empty ({profile_path})"
                )

    for index, raw_dir in enumerate(cli_management_raw.get("layout", {}).get("extra_dirs", [])):
        if not isinstance(raw_dir, str) or not raw_dir.strip():
            raise RuntimeError(
                f"Adapter profile invalid cli_management.layout.extra_dirs[{index}]: empty ({profile_path})"
            )
        if Path(raw_dir.strip()).is_absolute():
            raise RuntimeError(
                f"Adapter profile invalid cli_management.layout.extra_dirs[{index}]: must be relative ({profile_path})"
            )

    bootstrap_target_raw = cli_management_raw.get("layout", {}).get("bootstrap_target_relpath")
    if not isinstance(bootstrap_target_raw, str) or not bootstrap_target_raw.strip():
        raise RuntimeError(
            f"Adapter profile invalid cli_management.layout.bootstrap_target_relpath: empty ({profile_path})"
        )
    if Path(bootstrap_target_raw.strip()).is_absolute():
        raise RuntimeError(
            f"Adapter profile invalid cli_management.layout.bootstrap_target_relpath: must be relative ({profile_path})"
        )

    return AdapterProfile(
        engine=engine,
        profile_path=profile_path,
        prompt_builder=PromptBuilderProfile(
            engine_key=str(prompt_raw["engine_key"]),
            default_template_path=prompt_raw.get("default_template_path"),
            fallback_inline=str(prompt_raw["fallback_inline"]),
            merge_input_if_no_parameter_schema=bool(prompt_raw["merge_input_if_no_parameter_schema"]),
            params_json_source=prompt_raw["params_json_source"],
            main_prompt_source=prompt_raw["main_prompt_source"],
            main_prompt_default_template=str(prompt_raw["main_prompt_default_template"]),
            include_input_file_name=bool(prompt_raw["include_input_file_name"]),
            include_skill_dir=bool(prompt_raw["include_skill_dir"]),
        ),
        session_codec=SessionCodecProfile(
            strategy=session_raw["strategy"],
            error_message=str(session_raw["error_message"]),
            error_prefix=session_raw.get("error_prefix"),
            required_type=session_raw.get("required_type"),
            id_field=session_raw.get("id_field"),
            recursive_key=session_raw.get("recursive_key"),
            fallback_text_finder=session_raw.get("fallback_text_finder"),
            json_lines_finder=session_raw.get("json_lines_finder"),
            regex_pattern=session_raw.get("regex_pattern"),
        ),
        attempt_workspace=AttemptWorkspaceProfile(
            workspace_subdir=str(workspace_raw["workspace_subdir"]),
            skills_subdir=str(workspace_raw["skills_subdir"]),
            use_config_parent_as_workspace=bool(workspace_raw["use_config_parent_as_workspace"]),
            unknown_fallback=bool(workspace_raw["unknown_fallback"]),
        ),
        config_assets=ConfigAssetsProfile(
            bootstrap_path=str(config_assets_raw["bootstrap_path"]),
            default_path=str(config_assets_raw["default_path"]),
            enforced_path=str(config_assets_raw["enforced_path"]),
            settings_schema_path=(
                str(config_assets_raw["settings_schema_path"])
                if config_assets_raw.get("settings_schema_path") is not None
                else None
            ),
            skill_defaults_path=(
                str(config_assets_raw["skill_defaults_path"])
                if config_assets_raw.get("skill_defaults_path") is not None
                else None
            ),
        ),
        model_catalog=ModelCatalogProfile(
            mode=model_catalog_raw["mode"],
            manifest_path=(
                str(model_catalog_raw["manifest_path"])
                if model_catalog_raw.get("manifest_path") is not None
                else None
            ),
            models_root=(
                str(model_catalog_raw["models_root"])
                if model_catalog_raw.get("models_root") is not None
                else None
            ),
            seed_path=(
                str(model_catalog_raw["seed_path"])
                if model_catalog_raw.get("seed_path") is not None
                else None
            ),
        ),
        cli_management=CliManagementProfile(
            package=str(cli_management_raw["package"]),
            binary_candidates=tuple(
                str(item)
                for item in cli_management_raw["binary_candidates"]
            ),
            credential_imports=tuple(
                CredentialImportProfile(
                    source=str(item["source"]),
                    target_relpath=str(item["target_relpath"]),
                    import_validator=(
                        cast(ImportValidatorName, str(item["import_validator"]))
                        if isinstance(item.get("import_validator"), str) and item.get("import_validator")
                        else None
                    ),
                    aliases=tuple(
                        str(alias).strip()
                        for alias in item.get("aliases", [])
                        if isinstance(alias, str) and alias.strip()
                    ),
                )
                for item in cli_management_raw["credential_imports"]
            ),
            credential_policy=CredentialPolicyProfile(
                mode=cli_management_raw["credential_policy"]["mode"],
                sources=tuple(
                    str(item)
                    for item in cli_management_raw["credential_policy"]["sources"]
                ),
                settings_validator=cli_management_raw["credential_policy"]["settings_validator"],
            ),
            resume_probe=ResumeProbeProfile(
                help_hints=tuple(
                    str(item)
                    for item in cli_management_raw["resume_probe"]["help_hints"]
                ),
                dynamic_args=tuple(
                    str(item)
                    for item in cli_management_raw["resume_probe"]["dynamic_args"]
                ),
            ),
            layout=LayoutProfile(
                extra_dirs=tuple(
                    str(item)
                    for item in cli_management_raw["layout"]["extra_dirs"]
                ),
                bootstrap_target_relpath=str(cli_management_raw["layout"]["bootstrap_target_relpath"]),
                bootstrap_format=cli_management_raw["layout"]["bootstrap_format"],
                normalize_strategy=cli_management_raw["layout"]["normalize_strategy"],
            ),
        ),
        parser_auth_patterns=ParserAuthPatternsProfile(
            rules=tuple(
                cast(dict[str, Any], dict(rule))
                for rule in parser_auth_patterns_raw.get("rules", [])
            )
        ),
        parser_structured_extract=(
            ParserStructuredExtractProfile(
                event_type=str(parser_structured_extract_raw["event_type"]),
                session_id_key=str(parser_structured_extract_raw["session_id_key"]),
                response_key=str(parser_structured_extract_raw["response_key"]),
                summary_max_chars=int(parser_structured_extract_raw["summary_max_chars"]),
            )
            if isinstance(parser_structured_extract_raw, dict)
            else None
        ),
    )


def load_adapter_profile(engine: str, profile_path: Path) -> AdapterProfile:
    if engine.strip().lower() not in keys.ENGINE_KEYS:
        raise RuntimeError(f"Unsupported adapter engine: {engine}")
    return _load_adapter_profile_cached(engine, str(profile_path.resolve()))


def validate_adapter_profiles(profile_paths: dict[str, Path]) -> dict[str, AdapterProfile]:
    loaded: dict[str, AdapterProfile] = {}
    for engine, profile_path in profile_paths.items():
        loaded[engine] = load_adapter_profile(engine, profile_path)
    return loaded
