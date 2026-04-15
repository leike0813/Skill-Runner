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


SessionStrategy = Literal["first_json_line", "json_recursive_key", "json_lines_scan", "regex_extract"]
SessionTextFinder = Literal["find_session_id_in_text"]
SessionJsonLineFinder = Literal["find_session_id"]
ModelCatalogMode = Literal["manifest", "runtime_probe"]
CredentialPolicyMode = Literal["all_of_sources", "any_of_sources"]
SettingsValidator = Literal["iflow_oauth_settings"]
BootstrapFormat = Literal["json", "text"]
NormalizeStrategy = Literal["iflow_settings_v1"]
ProcessEventType = Literal["reasoning", "tool_call", "command_execution"]
UiShellSandboxProbeStrategy = Literal[
    "static_supported",
    "static_unsupported",
    "codex_landlock",
    "gemini_container",
]
UiShellAuthHintStrategy = Literal["none", "gemini_api_key_disables_sandbox"]
UiShellRuntimeOverrideStrategy = Literal["none", "gemini_ui_shell", "claude_ui_shell"]
StructuredOutputMode = Literal["noop", "canonical_passthrough", "compat_translate"]
StructuredOutputCliSchemaStrategy = Literal["noop", "path_schema_artifact", "inline_schema_object"]
StructuredOutputCompatSchemaStrategy = Literal["noop", "canonical_passthrough", "compat_translate"]
StructuredOutputPromptContractStrategy = Literal["canonical_summary", "compat_summary"]
StructuredOutputPayloadCanonicalizer = Literal["noop", "payload_union_object_canonicalizer"]
ImportValidatorName = Literal[
    "json_object",
    "codex_auth_json",
    "gemini_google_accounts_json",
    "gemini_oauth_creds_json",
    "iflow_accounts_json",
    "iflow_oauth_creds_json",
    "opencode_auth_json",
    "opencode_antigravity_accounts_json",
    "qwen_oauth_creds_json",
]


@dataclass(frozen=True)
class PromptBuilderProfile:
    skill_invoke_line_template: str
    body_prefix_extra_block: str
    body_suffix_extra_block: str


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
class ProviderContractProfile:
    multi_provider: bool
    canonical_provider_id: str | None


@dataclass(frozen=True)
class CommandDefaultsProfile:
    start: tuple[str, ...]
    resume: tuple[str, ...]
    ui_shell: tuple[str, ...]


@dataclass(frozen=True)
class CommandFeaturesProfile:
    inject_output_schema_cli: bool


@dataclass(frozen=True)
class StructuredOutputProfile:
    mode: StructuredOutputMode
    cli_schema_strategy: StructuredOutputCliSchemaStrategy
    compat_schema_strategy: StructuredOutputCompatSchemaStrategy
    prompt_contract_strategy: StructuredOutputPromptContractStrategy
    payload_canonicalizer: StructuredOutputPayloadCanonicalizer


@dataclass(frozen=True)
class UiShellConfigAssetsProfile:
    default_path: str | None
    enforced_path: str | None
    settings_schema_path: str | None
    target_relpath: str | None


@dataclass(frozen=True)
class UiShellProfile:
    command_id: str
    label: str
    trust_bootstrap_parent: bool
    sandbox_arg: str | None
    retry_without_sandbox_on_early_exit: bool
    sandbox_probe_strategy: UiShellSandboxProbeStrategy
    sandbox_probe_message: str | None
    auth_hint_strategy: UiShellAuthHintStrategy
    runtime_override_strategy: UiShellRuntimeOverrideStrategy
    config_assets: UiShellConfigAssetsProfile


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
class ProcessItemMappingProfile:
    item_type: str
    process_type: ProcessEventType
    summary_field: str | None
    text_field: str | None
    classification: str | None


@dataclass(frozen=True)
class ParserProcessExtractProfile:
    turn_start_payload_types: tuple[str, ...]
    turn_end_payload_types: tuple[str, ...]
    item_type_mappings: tuple[ProcessItemMappingProfile, ...]


@dataclass(frozen=True)
class AdapterProfile:
    engine: str
    profile_path: Path
    provider_contract: ProviderContractProfile
    prompt_builder: PromptBuilderProfile
    session_codec: SessionCodecProfile
    attempt_workspace: AttemptWorkspaceProfile
    config_assets: ConfigAssetsProfile
    model_catalog: ModelCatalogProfile
    command_defaults: CommandDefaultsProfile
    command_features: CommandFeaturesProfile
    structured_output: StructuredOutputProfile
    ui_shell: UiShellProfile
    cli_management: CliManagementProfile
    parser_auth_patterns: ParserAuthPatternsProfile
    parser_structured_extract: ParserStructuredExtractProfile | None
    parser_process_extract: ParserProcessExtractProfile | None

    def _resolve_profile_relative_path(self, path_value: str | None) -> Path | None:
        if not isinstance(path_value, str) or not path_value.strip():
            return None
        candidate = Path(path_value.strip())
        if not candidate.is_absolute():
            candidate = (self.profile_path.parent / candidate).resolve()
        return candidate

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

    def resolve_ui_shell_default_config_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.ui_shell.config_assets.default_path)

    def resolve_ui_shell_enforced_config_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.ui_shell.config_assets.enforced_path)

    def resolve_ui_shell_settings_schema_path(self) -> Path | None:
        return self._resolve_profile_relative_path(self.ui_shell.config_assets.settings_schema_path)

    def resolve_ui_shell_target_relpath(self) -> str | None:
        raw = self.ui_shell.config_assets.target_relpath
        if not isinstance(raw, str) or not raw.strip():
            return None
        return raw.strip()

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

    def resolve_command_defaults(self, *, action: str) -> list[str]:
        if action == "start":
            return list(self.command_defaults.start)
        if action == "resume":
            return list(self.command_defaults.resume)
        if action == "ui_shell":
            return list(self.command_defaults.ui_shell)
        return []

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


def _is_absolute_relpath_like(raw_value: str) -> bool:
    normalized = raw_value.strip()
    if not normalized:
        return False
    candidate = Path(normalized)
    if candidate.is_absolute():
        return True
    # On Windows, Path("/tmp/x").is_absolute() is False; treat rooted paths as absolute-like.
    return normalized.startswith(("/", "\\"))


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
    provider_contract_raw = payload["provider_contract"]
    session_raw = payload["session_codec"]
    workspace_raw = payload["attempt_workspace"]
    config_assets_raw = payload["config_assets"]
    model_catalog_raw = payload["model_catalog"]
    command_defaults_raw = payload["command_defaults"]
    command_features_raw = payload.get("command_features", {})
    structured_output_raw = payload.get("structured_output", {})
    ui_shell_raw = payload["ui_shell"]
    cli_management_raw = payload["cli_management"]
    parser_auth_patterns_raw = payload["parser_auth_patterns"]
    parser_structured_extract_raw = payload.get("parser_structured_extract")
    parser_process_extract_raw = payload.get("parser_process_extract")

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
    for label, raw_value in (
        ("ui_shell.config_assets.default_path", ui_shell_raw.get("config_assets", {}).get("default_path")),
        ("ui_shell.config_assets.enforced_path", ui_shell_raw.get("config_assets", {}).get("enforced_path")),
        (
            "ui_shell.config_assets.settings_schema_path",
            ui_shell_raw.get("config_assets", {}).get("settings_schema_path"),
        ),
    ):
        _validate_resolved_path(
            profile_path=profile_path,
            label=label,
            raw_value=raw_value,
        )

    ui_shell_target_raw = ui_shell_raw.get("config_assets", {}).get("target_relpath")
    if ui_shell_target_raw is not None:
        if not isinstance(ui_shell_target_raw, str) or not ui_shell_target_raw.strip():
            raise RuntimeError(
                f"Adapter profile invalid ui_shell.config_assets.target_relpath: empty ({profile_path})"
            )
        if _is_absolute_relpath_like(ui_shell_target_raw):
            raise RuntimeError(
                f"Adapter profile invalid ui_shell.config_assets.target_relpath: must be relative ({profile_path})"
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
        if _is_absolute_relpath_like(target_raw):
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
        if _is_absolute_relpath_like(raw_dir):
            raise RuntimeError(
                f"Adapter profile invalid cli_management.layout.extra_dirs[{index}]: must be relative ({profile_path})"
            )

    bootstrap_target_raw = cli_management_raw.get("layout", {}).get("bootstrap_target_relpath")
    if not isinstance(bootstrap_target_raw, str) or not bootstrap_target_raw.strip():
        raise RuntimeError(
            f"Adapter profile invalid cli_management.layout.bootstrap_target_relpath: empty ({profile_path})"
        )
    if _is_absolute_relpath_like(bootstrap_target_raw):
        raise RuntimeError(
            f"Adapter profile invalid cli_management.layout.bootstrap_target_relpath: must be relative ({profile_path})"
        )

    return AdapterProfile(
        engine=engine,
        profile_path=profile_path,
        provider_contract=ProviderContractProfile(
            multi_provider=bool(provider_contract_raw["multi_provider"]),
            canonical_provider_id=(
                str(provider_contract_raw["canonical_provider_id"])
                if provider_contract_raw.get("canonical_provider_id") is not None
                else None
            ),
        ),
        prompt_builder=PromptBuilderProfile(
            skill_invoke_line_template=str(prompt_raw["skill_invoke_line_template"]),
            body_prefix_extra_block=str(prompt_raw.get("body_prefix_extra_block") or ""),
            body_suffix_extra_block=str(prompt_raw.get("body_suffix_extra_block") or ""),
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
        command_defaults=CommandDefaultsProfile(
            start=tuple(str(item) for item in command_defaults_raw["start"]),
            resume=tuple(str(item) for item in command_defaults_raw["resume"]),
            ui_shell=tuple(str(item) for item in command_defaults_raw["ui_shell"]),
        ),
        command_features=CommandFeaturesProfile(
            inject_output_schema_cli=bool(command_features_raw.get("inject_output_schema_cli", False)),
        ),
        structured_output=StructuredOutputProfile(
            mode=cast(
                StructuredOutputMode,
                str(structured_output_raw.get("mode", "noop")),
            ),
            cli_schema_strategy=cast(
                StructuredOutputCliSchemaStrategy,
                str(structured_output_raw.get("cli_schema_strategy", "noop")),
            ),
            compat_schema_strategy=cast(
                StructuredOutputCompatSchemaStrategy,
                str(structured_output_raw.get("compat_schema_strategy", "noop")),
            ),
            prompt_contract_strategy=cast(
                StructuredOutputPromptContractStrategy,
                str(structured_output_raw.get("prompt_contract_strategy", "canonical_summary")),
            ),
            payload_canonicalizer=cast(
                StructuredOutputPayloadCanonicalizer,
                str(structured_output_raw.get("payload_canonicalizer", "noop")),
            ),
        ),
        ui_shell=UiShellProfile(
            command_id=str(ui_shell_raw["command_id"]),
            label=str(ui_shell_raw["label"]),
            trust_bootstrap_parent=bool(ui_shell_raw["trust_bootstrap_parent"]),
            sandbox_arg=(
                str(ui_shell_raw["sandbox_arg"])
                if ui_shell_raw.get("sandbox_arg") is not None
                else None
            ),
            retry_without_sandbox_on_early_exit=bool(ui_shell_raw["retry_without_sandbox_on_early_exit"]),
            sandbox_probe_strategy=ui_shell_raw["sandbox_probe_strategy"],
            sandbox_probe_message=(
                str(ui_shell_raw["sandbox_probe_message"])
                if ui_shell_raw.get("sandbox_probe_message") is not None
                else None
            ),
            auth_hint_strategy=ui_shell_raw["auth_hint_strategy"],
            runtime_override_strategy=ui_shell_raw["runtime_override_strategy"],
            config_assets=UiShellConfigAssetsProfile(
                default_path=(
                    str(ui_shell_raw["config_assets"]["default_path"])
                    if ui_shell_raw["config_assets"].get("default_path") is not None
                    else None
                ),
                enforced_path=(
                    str(ui_shell_raw["config_assets"]["enforced_path"])
                    if ui_shell_raw["config_assets"].get("enforced_path") is not None
                    else None
                ),
                settings_schema_path=(
                    str(ui_shell_raw["config_assets"]["settings_schema_path"])
                    if ui_shell_raw["config_assets"].get("settings_schema_path") is not None
                    else None
                ),
                target_relpath=(
                    str(ui_shell_raw["config_assets"]["target_relpath"])
                    if ui_shell_raw["config_assets"].get("target_relpath") is not None
                    else None
                ),
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
        parser_process_extract=(
            ParserProcessExtractProfile(
                turn_start_payload_types=tuple(
                    str(item)
                    for item in parser_process_extract_raw.get("turn_start_payload_types", [])
                    if isinstance(item, str) and item
                ),
                turn_end_payload_types=tuple(
                    str(item)
                    for item in parser_process_extract_raw.get("turn_end_payload_types", [])
                    if isinstance(item, str) and item
                ),
                item_type_mappings=tuple(
                    ProcessItemMappingProfile(
                        item_type=str(item["item_type"]),
                        process_type=cast(ProcessEventType, str(item["process_type"])),
                        summary_field=(
                            str(item["summary_field"])
                            if isinstance(item.get("summary_field"), str) and item.get("summary_field")
                            else None
                        ),
                        text_field=(
                            str(item["text_field"])
                            if isinstance(item.get("text_field"), str) and item.get("text_field")
                            else None
                        ),
                        classification=(
                            str(item["classification"])
                            if isinstance(item.get("classification"), str) and item.get("classification")
                            else None
                        ),
                    )
                    for item in parser_process_extract_raw.get("item_type_mappings", [])
                    if isinstance(item, dict)
                ),
            )
            if isinstance(parser_process_extract_raw, dict)
            else None
        ),
    )


def load_adapter_profile(engine: str, profile_path: Path) -> AdapterProfile:
    if engine.strip().lower() not in keys.ENGINE_KEYS:
        raise RuntimeError(f"Unsupported adapter engine: {engine}")
    return _load_adapter_profile_cached(engine, str(profile_path.resolve()))


def adapter_profile_path_for_engine(engine: str) -> Path:
    normalized = engine.strip().lower()
    if normalized not in keys.ENGINE_KEYS:
        raise RuntimeError(f"Unsupported adapter engine: {engine}")
    return config_registry.root / "server" / "engines" / normalized / "adapter" / "adapter_profile.json"


def validate_adapter_profiles(profile_paths: dict[str, Path]) -> dict[str, AdapterProfile]:
    loaded: dict[str, AdapterProfile] = {}
    for engine, profile_path in profile_paths.items():
        loaded[engine] = load_adapter_profile(engine, profile_path)
    return loaded
