from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from server.services.mcp.registry import (
    McpConfigError,
    McpResolution,
    McpServerDefinition,
    SecretResolver,
)

from .state_paths import (
    active_claude_state_path,
    read_claude_state_payload,
    write_claude_state_payload,
)

_SIDECAR_NAME = "skill-runner-managed-mcp.json"


def materialize_claude_mcp_resolution(
    *,
    agent_home: Path,
    run_dir: Path,
    resolution: McpResolution,
    secret_resolver: SecretResolver,
) -> None:
    if not resolution.servers:
        return
    payload = read_claude_state_payload(agent_home)
    sidecar = _read_sidecar(agent_home)
    run_key = str(run_dir.resolve())
    top_level = _ensure_mapping(payload, "mcpServers")
    project_servers: dict[str, Any] | None = None

    managed_top = set(_normalize_string_list(sidecar.get("agent_home")))
    projects_sidecar = sidecar.setdefault("projects", {})
    if not isinstance(projects_sidecar, dict):
        projects_sidecar = {}
        sidecar["projects"] = projects_sidecar
    managed_project: set[str] | None = None

    for server in resolution.servers:
        rendered = render_claude_mcp_server_payload(
            server.definition,
            secret_resolver=secret_resolver,
        )
        if server.scope == "agent-home":
            top_level[server.definition.id] = rendered
            managed_top.add(server.definition.id)
        else:
            if project_servers is None:
                projects = _ensure_mapping(payload, "projects")
                project_payload = _ensure_mapping(projects, run_key)
                project_servers = _ensure_mapping(project_payload, "mcpServers")
                managed_project = set(_normalize_string_list(projects_sidecar.get(run_key)))
            assert managed_project is not None
            project_servers[server.definition.id] = rendered
            managed_project.add(server.definition.id)

    sidecar["agent_home"] = sorted(managed_top)
    if managed_project is not None:
        projects_sidecar[run_key] = sorted(managed_project)
    write_claude_state_payload(active_claude_state_path(agent_home), payload)
    _write_sidecar(agent_home, sidecar)


def sync_claude_agent_home_mcp(
    *,
    agent_home: Path,
    registry: Mapping[str, McpServerDefinition],
    secret_resolver: SecretResolver,
) -> None:
    payload = read_claude_state_payload(agent_home)
    sidecar = _read_sidecar(agent_home)
    top_level = _ensure_mapping(payload, "mcpServers")
    previous_managed = set(_normalize_string_list(sidecar.get("agent_home")))
    next_managed: set[str] = set()

    for server_id in sorted(previous_managed):
        top_level.pop(server_id, None)

    for definition in registry.values():
        if definition.activation != "default":
            continue
        if definition.scope != "agent-home":
            continue
        if "claude" not in definition.effective_engines:
            continue
        top_level[definition.id] = render_claude_mcp_server_payload(
            definition,
            secret_resolver=secret_resolver,
        )
        next_managed.add(definition.id)

    sidecar["agent_home"] = sorted(next_managed)
    write_claude_state_payload(active_claude_state_path(agent_home), payload)
    _write_sidecar(agent_home, sidecar)


def remove_claude_agent_home_mcp(*, agent_home: Path, server_id: str) -> None:
    payload = read_claude_state_payload(agent_home)
    sidecar = _read_sidecar(agent_home)
    managed = set(_normalize_string_list(sidecar.get("agent_home")))
    if server_id in managed:
        top_level = _ensure_mapping(payload, "mcpServers")
        top_level.pop(server_id, None)
        managed.remove(server_id)
        sidecar["agent_home"] = sorted(managed)
        write_claude_state_payload(active_claude_state_path(agent_home), payload)
        _write_sidecar(agent_home, sidecar)


def cleanup_claude_run_local_mcp(*, agent_home: Path, run_dir: Path) -> None:
    run_key = str(run_dir.resolve())
    payload = read_claude_state_payload(agent_home)
    sidecar = _read_sidecar(agent_home)
    projects_sidecar = sidecar.get("projects")
    if not isinstance(projects_sidecar, dict):
        return
    managed = set(_normalize_string_list(projects_sidecar.get(run_key)))
    if not managed:
        return
    projects = payload.get("projects")
    if isinstance(projects, dict):
        project_payload = projects.get(run_key)
        if isinstance(project_payload, dict):
            servers = project_payload.get("mcpServers")
            if isinstance(servers, dict):
                for server_id in managed:
                    servers.pop(server_id, None)
                if not servers:
                    project_payload.pop("mcpServers", None)
    projects_sidecar.pop(run_key, None)
    write_claude_state_payload(active_claude_state_path(agent_home), payload)
    _write_sidecar(agent_home, sidecar)


def render_claude_mcp_server_payload(
    definition: McpServerDefinition,
    *,
    secret_resolver: SecretResolver,
) -> dict[str, Any]:
    if definition.transport == "stdio":
        if not definition.command:
            raise McpConfigError(f"MCP server '{definition.id}' requires command")
        payload: dict[str, Any] = {
            "type": "stdio",
            "command": definition.command,
        }
        if definition.args:
            payload["args"] = list(definition.args)
        env_payload = _resolve_env(definition, secret_resolver)
        if env_payload:
            payload["env"] = env_payload
        return payload
    if not definition.url:
        raise McpConfigError(f"MCP server '{definition.id}' requires url")
    payload = {
        "type": definition.transport,
        "url": definition.url,
    }
    header_payload = _resolve_headers(definition, secret_resolver)
    if header_payload:
        payload["headers"] = header_payload
    return payload


def _resolve_env(
    definition: McpServerDefinition,
    secret_resolver: SecretResolver,
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for item in definition.auth_env:
        secret = secret_resolver(item.secret_id)
        if secret is None:
            raise McpConfigError(
                f"MCP server '{definition.id}' references missing secret '{item.secret_id}'"
            )
        resolved[item.name] = secret
    return resolved


def _resolve_headers(
    definition: McpServerDefinition,
    secret_resolver: SecretResolver,
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for item in definition.auth_headers:
        secret = secret_resolver(item.secret_id)
        if secret is None:
            raise McpConfigError(
                f"MCP server '{definition.id}' references missing secret '{item.secret_id}'"
            )
        resolved[item.name] = f"{item.prefix}{secret}"
    return resolved


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    current = parent.get(key)
    if not isinstance(current, dict):
        current = {}
        parent[key] = current
    return current


def _sidecar_path(agent_home: Path) -> Path:
    return agent_home / ".claude" / _SIDECAR_NAME


def _read_sidecar(agent_home: Path) -> dict[str, Any]:
    path = _sidecar_path(agent_home)
    if not path.exists():
        return {"version": 1, "agent_home": [], "projects": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"version": 1, "agent_home": [], "projects": {}}
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return {"version": 1, "agent_home": [], "projects": {}}
    if not isinstance(payload.get("agent_home"), list):
        payload["agent_home"] = []
    if not isinstance(payload.get("projects"), dict):
        payload["projects"] = {}
    return payload


def _write_sidecar(agent_home: Path, payload: Mapping[str, Any]) -> None:
    path = _sidecar_path(agent_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]
