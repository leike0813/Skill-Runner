from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

import jsonschema  # type: ignore[import-untyped]

from server.config import config
from server.models import SkillManifest
from server.services.engine_management.model_registry import supported_engines

MCP_ROOT_KEYS = frozenset({"mcpServers", "mcp_servers", "mcp"})
_ASSET_REGISTRY_PATH = Path(config.SYSTEM.ROOT) / "server" / "assets" / "configs" / "mcp_registry.json"
_REGISTRY_SCHEMA_PATH = Path(config.SYSTEM.ROOT) / "server" / "contracts" / "schemas" / "mcp_registry.schema.json"
_EMPTY_REGISTRY_PAYLOAD: dict[str, Any] = {"version": 1, "servers": {}}
SecretResolver = Callable[[str], str | None]


class McpConfigError(ValueError):
    """Raised when governed MCP policy rejects a run configuration."""


@dataclass(frozen=True)
class McpAuthEnvRef:
    name: str
    secret_id: str


@dataclass(frozen=True)
class McpAuthHeaderRef:
    name: str
    secret_id: str
    prefix: str = ""


@dataclass(frozen=True)
class McpServerDefinition:
    id: str
    activation: Literal["default", "declared"]
    effective_engines: tuple[str, ...]
    scope: Literal["run-local", "agent-home"]
    transport: Literal["stdio", "http", "sse"]
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    auth_env: tuple[McpAuthEnvRef, ...] = ()
    auth_headers: tuple[McpAuthHeaderRef, ...] = ()


@dataclass(frozen=True)
class ResolvedMcpServer:
    definition: McpServerDefinition
    scope: Literal["run-local", "agent-home"]


@dataclass(frozen=True)
class McpResolution:
    servers: tuple[ResolvedMcpServer, ...]

    @property
    def has_declared(self) -> bool:
        return any(server.definition.activation == "declared" for server in self.servers)


def validate_no_mcp_root_keys(payload: Mapping[str, Any] | None, *, source: str) -> None:
    if not isinstance(payload, Mapping):
        return
    blocked = sorted(key for key in payload.keys() if isinstance(key, str) and key in MCP_ROOT_KEYS)
    if blocked:
        raise McpConfigError(
            f"{source} must not define MCP root key(s): {', '.join(blocked)}. "
            "Use runner.json mcp.required_servers and the system MCP registry instead."
        )


def asset_mcp_registry_path() -> Path:
    return _ASSET_REGISTRY_PATH


def runtime_mcp_registry_path() -> Path:
    return Path(config.SYSTEM.MCP_REGISTRY_FILE)


def effective_mcp_registry_path() -> Path:
    runtime_path = runtime_mcp_registry_path()
    if runtime_path.exists():
        return runtime_path
    return asset_mcp_registry_path()


def clear_mcp_registry_cache() -> None:
    _load_mcp_registry_cached.cache_clear()


def load_mcp_registry_payload(registry_path: Path | None = None) -> dict[str, Any]:
    path = registry_path or effective_mcp_registry_path()
    return _read_registry_payload(path, recover_invalid=path != asset_mcp_registry_path())


def validate_mcp_registry_payload(payload: Mapping[str, Any]) -> None:
    schema = json.loads(_REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


def write_runtime_mcp_registry_payload(
    payload: Mapping[str, Any],
    registry_path: Path | None = None,
) -> None:
    validate_mcp_registry_payload(payload)
    _parse_registry_payload(payload)
    path = registry_path or runtime_mcp_registry_path()
    _atomic_write_json(path, dict(payload), mode=0o644)
    clear_mcp_registry_cache()


def load_mcp_registry(registry_path: Path | None = None) -> dict[str, McpServerDefinition]:
    path = registry_path or effective_mcp_registry_path()
    return _load_mcp_registry_cached(str(path.resolve()))


@lru_cache(maxsize=16)
def _load_mcp_registry_cached(registry_path: str) -> dict[str, McpServerDefinition]:
    path = Path(registry_path)
    payload = _read_registry_payload(path, recover_invalid=path == runtime_mcp_registry_path())
    return _parse_registry_payload(payload)


def _read_registry_payload(path: Path, *, recover_invalid: bool) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if not recover_invalid:
            raise
        _backup_invalid_file(path)
        _atomic_write_json(path, _EMPTY_REGISTRY_PAYLOAD, mode=0o644)
        payload = dict(_EMPTY_REGISTRY_PAYLOAD)
    validate_mcp_registry_payload(payload)
    if not isinstance(payload, dict):
        raise McpConfigError("MCP registry payload must be an object")
    return payload


def _parse_registry_payload(payload: Mapping[str, Any]) -> dict[str, McpServerDefinition]:
    servers_obj = payload.get("servers")
    if not isinstance(servers_obj, dict):
        raise McpConfigError("MCP registry servers must be an object")

    registry: dict[str, McpServerDefinition] = {}
    for server_id, raw_server in servers_obj.items():
        if not isinstance(server_id, str) or not isinstance(raw_server, dict):
            raise McpConfigError("MCP registry server entries must be object mappings")
        registry[server_id] = _build_server_definition(server_id, raw_server)
    return registry


def _backup_invalid_file(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.name}.invalid.bak")
    if backup.exists():
        backup.unlink()
    path.replace(backup)


def _atomic_write_json(path: Path, payload: Mapping[str, Any], *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    try:
        path.chmod(mode)
    except OSError:
        pass


def _build_server_definition(server_id: str, raw_server: dict[str, Any]) -> McpServerDefinition:
    all_supported = supported_engines()
    effective_engines = _resolve_effective_engines(
        engines=raw_server.get("engines"),
        unsupported_engines=raw_server.get("unsupported_engines"),
        all_supported=all_supported,
        server_id=server_id,
    )
    activation = raw_server["activation"]
    scope = raw_server["scope"]
    transport = raw_server["transport"]
    auth_env, auth_headers = _parse_auth_refs(server_id, raw_server.get("auth"))
    return McpServerDefinition(
        id=server_id,
        activation=activation,
        effective_engines=tuple(effective_engines),
        scope=scope,
        transport=transport,
        command=raw_server.get("command"),
        args=tuple(str(item) for item in raw_server.get("args", [])),
        url=raw_server.get("url"),
        auth_env=auth_env,
        auth_headers=auth_headers,
    )


def _parse_auth_refs(
    server_id: str,
    raw_auth: Any,
) -> tuple[tuple[McpAuthEnvRef, ...], tuple[McpAuthHeaderRef, ...]]:
    if raw_auth is None:
        return (), ()
    if not isinstance(raw_auth, dict):
        raise McpConfigError(f"MCP registry server '{server_id}' auth must be an object")
    env_refs: list[McpAuthEnvRef] = []
    seen_env: set[str] = set()
    for item in raw_auth.get("env") or []:
        name = str(item.get("name", "")).strip()
        secret_id = str(item.get("secret_id", "")).strip()
        if not name or not secret_id:
            raise McpConfigError(
                f"MCP registry server '{server_id}' auth.env entries require name and secret_id"
            )
        if name in seen_env:
            raise McpConfigError(
                f"MCP registry server '{server_id}' auth.env duplicates name '{name}'"
            )
        seen_env.add(name)
        env_refs.append(McpAuthEnvRef(name=name, secret_id=secret_id))

    header_refs: list[McpAuthHeaderRef] = []
    seen_headers: set[str] = set()
    for item in raw_auth.get("headers") or []:
        name = str(item.get("name", "")).strip()
        secret_id = str(item.get("secret_id", "")).strip()
        prefix = str(item.get("prefix", ""))
        if not name or not secret_id:
            raise McpConfigError(
                f"MCP registry server '{server_id}' auth.headers entries require name and secret_id"
            )
        normalized_name = name.lower()
        if normalized_name in seen_headers:
            raise McpConfigError(
                f"MCP registry server '{server_id}' auth.headers duplicates name '{name}'"
            )
        seen_headers.add(normalized_name)
        header_refs.append(McpAuthHeaderRef(name=name, secret_id=secret_id, prefix=prefix))
    return tuple(env_refs), tuple(header_refs)


def _resolve_effective_engines(
    *,
    engines: Any,
    unsupported_engines: Any,
    all_supported: list[str],
    server_id: str,
) -> list[str]:
    declared = _normalize_engine_list(engines, field_name=f"{server_id}.engines")
    unsupported = _normalize_engine_list(
        unsupported_engines,
        field_name=f"{server_id}.unsupported_engines",
    )
    supported = set(all_supported)
    unknown = sorted((set(declared) | set(unsupported)) - supported)
    if unknown:
        raise McpConfigError(
            f"MCP registry server '{server_id}' references unknown engine(s): {', '.join(unknown)}"
        )
    overlap = sorted(set(declared) & set(unsupported))
    if overlap:
        raise McpConfigError(
            f"MCP registry server '{server_id}' engines and unsupported_engines overlap: "
            + ", ".join(overlap)
        )
    base = declared if declared else list(all_supported)
    denied = set(unsupported)
    effective = [engine for engine in base if engine not in denied]
    if not effective:
        raise McpConfigError(f"MCP registry server '{server_id}' effective engines must not be empty")
    return effective


def _normalize_engine_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise McpConfigError(f"MCP registry {field_name} must be a list when provided")
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise McpConfigError(f"MCP registry {field_name} must contain non-empty strings")
        normalized.append(item.strip())
    return list(dict.fromkeys(normalized))


def resolve_mcp_servers(
    *,
    skill: SkillManifest,
    engine: str,
    registry: Mapping[str, McpServerDefinition] | None = None,
    registry_path: Path | None = None,
) -> McpResolution:
    normalized_engine = engine.strip()
    if normalized_engine not in supported_engines():
        raise McpConfigError(f"Unknown engine for MCP resolution: {engine}")
    loaded_registry = dict(registry) if registry is not None else load_mcp_registry(registry_path)
    required_ids = _skill_required_mcp_servers(skill)

    resolved: list[ResolvedMcpServer] = []
    for definition in loaded_registry.values():
        if definition.activation != "default":
            continue
        if normalized_engine in definition.effective_engines:
            resolved.append(ResolvedMcpServer(definition=definition, scope=definition.scope))

    for server_id in required_ids:
        requested_definition = loaded_registry.get(server_id)
        if requested_definition is None:
            raise McpConfigError(f"Skill '{skill.id}' requires unknown MCP server '{server_id}'")
        if requested_definition.activation != "declared":
            raise McpConfigError(
                f"Skill '{skill.id}' may only require declared MCP servers; '{server_id}' is "
                f"{requested_definition.activation}"
            )
        if normalized_engine not in requested_definition.effective_engines:
            raise McpConfigError(
                f"Skill '{skill.id}' requires MCP server '{server_id}', but it does not support "
                f"engine '{normalized_engine}'"
            )
        resolved.append(ResolvedMcpServer(definition=requested_definition, scope="run-local"))

    return McpResolution(servers=tuple(resolved))


def _skill_required_mcp_servers(skill: SkillManifest) -> list[str]:
    mcp_obj = getattr(skill, "mcp", None)
    raw = getattr(mcp_obj, "required_servers", None)
    if raw is None and isinstance(mcp_obj, dict):
        raw = mcp_obj.get("required_servers")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise McpConfigError(f"Skill '{skill.id}' mcp.required_servers must be a list")
    required: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise McpConfigError(
                f"Skill '{skill.id}' mcp.required_servers must contain non-empty strings"
            )
        normalized = item.strip()
        if normalized not in required:
            required.append(normalized)
    return required


def render_mcp_config(
    engine: str,
    servers: tuple[ResolvedMcpServer, ...],
    *,
    secret_resolver: SecretResolver | None = None,
) -> dict[str, Any]:
    if not servers:
        return {}
    root = _engine_mcp_root(engine)
    return {
        root: {
            server.definition.id: _render_server_payload(
                engine,
                server.definition,
                secret_resolver=secret_resolver,
            )
            for server in servers
        }
    }


def _engine_mcp_root(engine: str) -> str:
    if engine == "codex":
        return "mcp_servers"
    if engine in {"gemini", "qwen", "claude"}:
        return "mcpServers"
    if engine == "opencode":
        return "mcp"
    raise McpConfigError(f"Unsupported MCP render engine: {engine}")


def _render_server_payload(
    engine: str,
    definition: McpServerDefinition,
    *,
    secret_resolver: SecretResolver | None,
) -> dict[str, Any]:
    if definition.transport == "stdio":
        payload: dict[str, Any] = {"command": definition.command}
        if definition.args:
            payload["args"] = list(definition.args)
        env_payload = _resolve_env_payload(definition, secret_resolver)
        if env_payload:
            payload["env"] = env_payload
        return payload
    payload = {"url": definition.url}
    header_payload = _resolve_header_payload(definition, secret_resolver)
    if header_payload:
        payload["http_headers" if engine == "codex" else "headers"] = header_payload
    return payload


def _resolve_env_payload(
    definition: McpServerDefinition,
    secret_resolver: SecretResolver | None,
) -> dict[str, str]:
    if not definition.auth_env:
        return {}
    if secret_resolver is None:
        raise McpConfigError(f"MCP server '{definition.id}' has env auth but no secret resolver")
    resolved: dict[str, str] = {}
    for item in definition.auth_env:
        secret = secret_resolver(item.secret_id)
        if secret is None:
            raise McpConfigError(
                f"MCP server '{definition.id}' references missing secret '{item.secret_id}'"
            )
        resolved[item.name] = secret
    return resolved


def _resolve_header_payload(
    definition: McpServerDefinition,
    secret_resolver: SecretResolver | None,
) -> dict[str, str]:
    if not definition.auth_headers:
        return {}
    if secret_resolver is None:
        raise McpConfigError(f"MCP server '{definition.id}' has header auth but no secret resolver")
    resolved: dict[str, str] = {}
    for item in definition.auth_headers:
        secret = secret_resolver(item.secret_id)
        if secret is None:
            raise McpConfigError(
                f"MCP server '{definition.id}' references missing secret '{item.secret_id}'"
            )
        resolved[item.name] = f"{item.prefix}{secret}"
    return resolved


def build_mcp_config_layer(
    *,
    skill: SkillManifest,
    engine: str,
    registry: Mapping[str, McpServerDefinition] | None = None,
    registry_path: Path | None = None,
    secret_resolver: SecretResolver | None = None,
) -> tuple[McpResolution, dict[str, Any]]:
    resolution = resolve_mcp_servers(
        skill=skill,
        engine=engine,
        registry=registry,
        registry_path=registry_path,
    )
    if secret_resolver is None:
        from .secret_store import mcp_secret_store

        secret_resolver = mcp_secret_store.get_secret
    return resolution, render_mcp_config(engine, resolution.servers, secret_resolver=secret_resolver)


def codex_run_profile_name(run_dir: Path) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_dir.name).strip(".-")
    if not suffix:
        suffix = "run"
    return f"skill-runner-run-{suffix}"
