from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from server.models import (
    ManagementMcpAuthEnvView,
    ManagementMcpAuthHeaderView,
    ManagementMcpAuthView,
    ManagementMcpServerListResponse,
    ManagementMcpServerUpsertRequest,
    ManagementMcpServerView,
)
from server.engines.claude.adapter.mcp_materializer import (
    remove_claude_agent_home_mcp,
    sync_claude_agent_home_mcp,
)
from server.config import config

from .registry import (
    McpConfigError,
    McpServerDefinition,
    clear_mcp_registry_cache,
    load_mcp_registry,
    load_mcp_registry_payload,
    write_runtime_mcp_registry_payload,
)
from .secret_store import McpSecretStore, mcp_secret_store

_SERVER_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass
class McpManagementService:
    secret_store: McpSecretStore = field(default_factory=lambda: mcp_secret_store)

    def list_servers(self) -> ManagementMcpServerListResponse:
        payload = load_mcp_registry_payload()
        registry = load_mcp_registry()
        servers_obj = payload.get("servers") if isinstance(payload, dict) else {}
        if not isinstance(servers_obj, dict):
            raise McpConfigError("MCP registry servers must be an object")
        views: list[ManagementMcpServerView] = []
        for server_id in sorted(servers_obj):
            raw_server = servers_obj.get(server_id)
            if not isinstance(raw_server, dict) or server_id not in registry:
                continue
            views.append(self._build_view(server_id, raw_server, registry[server_id].effective_engines))
        return ManagementMcpServerListResponse(servers=views)

    def upsert_server(
        self,
        *,
        server_id: str,
        request: ManagementMcpServerUpsertRequest,
    ) -> ManagementMcpServerView:
        normalized_id = self._normalize_server_id(server_id)
        payload = load_mcp_registry_payload()
        servers_obj = payload.setdefault("servers", {})
        if not isinstance(servers_obj, dict):
            raise McpConfigError("MCP registry servers must be an object")
        existing = servers_obj.get(normalized_id)
        existing_server = existing if isinstance(existing, dict) else {}

        raw_server, upsert_secrets, delete_secrets = self._build_registry_server(
            normalized_id,
            request,
            existing_server,
        )
        next_payload = dict(payload)
        next_servers = dict(servers_obj)
        next_servers[normalized_id] = raw_server
        next_payload["servers"] = next_servers

        for secret_id, value in upsert_secrets.items():
            self.secret_store.upsert_secret(secret_id, value)
        write_runtime_mcp_registry_payload(next_payload)
        self.secret_store.delete_secrets(delete_secrets)
        clear_mcp_registry_cache()

        registry = load_mcp_registry()
        self._sync_claude_agent_home(registry)
        return self._build_view(normalized_id, raw_server, registry[normalized_id].effective_engines)

    def delete_server(self, server_id: str) -> bool:
        normalized_id = self._normalize_server_id(server_id)
        payload = load_mcp_registry_payload()
        servers_obj = payload.get("servers")
        if not isinstance(servers_obj, dict):
            raise McpConfigError("MCP registry servers must be an object")
        existing = servers_obj.get(normalized_id)
        if not isinstance(existing, dict):
            return False
        next_payload = dict(payload)
        next_servers = dict(servers_obj)
        del next_servers[normalized_id]
        next_payload["servers"] = next_servers
        write_runtime_mcp_registry_payload(next_payload)
        self.secret_store.delete_secrets(self._collect_secret_ids(existing))
        clear_mcp_registry_cache()
        remove_claude_agent_home_mcp(
            agent_home=self._agent_home(),
            server_id=normalized_id,
        )
        return True

    def _build_registry_server(
        self,
        server_id: str,
        request: ManagementMcpServerUpsertRequest,
        existing: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str], set[str]]:
        raw_server: dict[str, Any] = {
            "activation": request.activation,
            "scope": request.scope,
            "transport": request.transport,
        }
        if request.engines:
            raw_server["engines"] = self._dedupe_nonempty(request.engines, "engines")
        unsupported = self._dedupe_nonempty(request.unsupported_engines, "unsupported_engines")
        if unsupported:
            raw_server["unsupported_engines"] = unsupported

        if request.transport == "stdio":
            command = (request.command or "").strip()
            if not command:
                raise McpConfigError("stdio MCP server requires command")
            raw_server["command"] = command
            args = [str(item) for item in request.args]
            if args:
                raw_server["args"] = args
        else:
            url = (request.url or "").strip()
            if not url:
                raise McpConfigError("http/sse MCP server requires url")
            raw_server["url"] = url

        auth_payload, upsert_secrets, delete_secrets = self._build_auth_payload(
            server_id,
            request,
            existing,
        )
        if auth_payload:
            raw_server["auth"] = auth_payload
        return raw_server, upsert_secrets, delete_secrets

    def _build_auth_payload(
        self,
        server_id: str,
        request: ManagementMcpServerUpsertRequest,
        existing: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str], set[str]]:
        existing_auth = existing.get("auth") if isinstance(existing, Mapping) else {}
        existing_auth = existing_auth if isinstance(existing_auth, Mapping) else {}
        existing_env = self._existing_refs_by_name(existing_auth.get("env"), case_sensitive=True)
        existing_headers = self._existing_refs_by_name(existing_auth.get("headers"), case_sensitive=False)
        keep_refs: set[str] = set()
        upsert_secrets: dict[str, str] = {}

        env_entries: list[dict[str, str]] = []
        seen_env: set[str] = set()
        for item in request.auth.env:
            name = item.name.strip()
            if not name:
                raise McpConfigError("auth.env name is required")
            if name in seen_env:
                raise McpConfigError(f"duplicate auth.env name '{name}'")
            seen_env.add(name)
            secret_id = existing_env.get(name) or self._secret_id(server_id, "env", name)
            if item.value is not None and item.value != "":
                upsert_secrets[secret_id] = item.value
            elif secret_id not in existing_env.values():
                raise McpConfigError(f"auth.env '{name}' requires a value")
            keep_refs.add(secret_id)
            env_entries.append({"name": name, "secret_id": secret_id})

        header_entries: list[dict[str, str]] = []
        seen_headers: set[str] = set()
        for header_item in request.auth.headers:
            name = header_item.name.strip()
            if not name:
                raise McpConfigError("auth.headers name is required")
            lookup = name.lower()
            if lookup in seen_headers:
                raise McpConfigError(f"duplicate auth.headers name '{name}'")
            seen_headers.add(lookup)
            secret_id = existing_headers.get(lookup) or self._secret_id(server_id, "header", name)
            if header_item.value is not None and header_item.value != "":
                upsert_secrets[secret_id] = header_item.value
            elif secret_id not in existing_headers.values():
                raise McpConfigError(f"auth.headers '{name}' requires a value")
            keep_refs.add(secret_id)
            entry = {"name": name, "secret_id": secret_id}
            if header_item.prefix:
                entry["prefix"] = header_item.prefix
            header_entries.append(entry)

        auth_payload: dict[str, Any] = {}
        if env_entries:
            auth_payload["env"] = env_entries
        if header_entries:
            auth_payload["headers"] = header_entries
        delete_secrets = self._collect_secret_ids(existing) - keep_refs
        return auth_payload, upsert_secrets, delete_secrets

    def _build_view(
        self,
        server_id: str,
        raw_server: Mapping[str, Any],
        effective_engines: tuple[str, ...],
    ) -> ManagementMcpServerView:
        auth = raw_server.get("auth") if isinstance(raw_server, Mapping) else {}
        auth = auth if isinstance(auth, Mapping) else {}
        env_views = [
            ManagementMcpAuthEnvView(
                name=str(item.get("name", "")),
                configured=self.secret_store.has_secret(str(item.get("secret_id", ""))),
                masked_value="********"
                if self.secret_store.has_secret(str(item.get("secret_id", "")))
                else "",
            )
            for item in auth.get("env", []) or []
            if isinstance(item, Mapping)
        ]
        header_views = [
            ManagementMcpAuthHeaderView(
                name=str(item.get("name", "")),
                prefix=str(item.get("prefix", "")),
                configured=self.secret_store.has_secret(str(item.get("secret_id", ""))),
                masked_value="********"
                if self.secret_store.has_secret(str(item.get("secret_id", "")))
                else "",
            )
            for item in auth.get("headers", []) or []
            if isinstance(item, Mapping)
        ]
        return ManagementMcpServerView(
            id=server_id,
            activation=raw_server["activation"],
            engines=list(raw_server["engines"]) if isinstance(raw_server.get("engines"), list) else None,
            unsupported_engines=list(raw_server.get("unsupported_engines") or []),
            effective_engines=list(effective_engines),
            scope=raw_server["scope"],
            transport=raw_server["transport"],
            command=raw_server.get("command") if isinstance(raw_server.get("command"), str) else None,
            args=list(raw_server.get("args") or []),
            url=raw_server.get("url") if isinstance(raw_server.get("url"), str) else None,
            auth=ManagementMcpAuthView(env=env_views, headers=header_views),
        )

    @staticmethod
    def _normalize_server_id(server_id: str) -> str:
        normalized = server_id.strip()
        if not normalized or not _SERVER_ID_RE.match(normalized):
            raise McpConfigError("MCP server id must match ^[A-Za-z0-9_.-]+$")
        return normalized

    @staticmethod
    def _dedupe_nonempty(values: list[str], field_name: str) -> list[str]:
        normalized: list[str] = []
        for item in values:
            value = str(item).strip()
            if not value:
                raise McpConfigError(f"{field_name} entries must be non-empty")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _existing_refs_by_name(raw: Any, *, case_sensitive: bool) -> dict[str, str]:
        refs: dict[str, str] = {}
        if not isinstance(raw, list):
            return refs
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name", "")).strip()
            secret_id = str(item.get("secret_id", "")).strip()
            if not name or not secret_id:
                continue
            refs[name if case_sensitive else name.lower()] = secret_id
        return refs

    @staticmethod
    def _collect_secret_ids(raw_server: Mapping[str, Any]) -> set[str]:
        auth = raw_server.get("auth") if isinstance(raw_server, Mapping) else {}
        auth = auth if isinstance(auth, Mapping) else {}
        secret_ids: set[str] = set()
        for section in ("env", "headers"):
            raw_entries = auth.get(section)
            if not isinstance(raw_entries, list):
                continue
            for item in raw_entries:
                if not isinstance(item, Mapping):
                    continue
                secret_id = str(item.get("secret_id", "")).strip()
                if secret_id:
                    secret_ids.add(secret_id)
        return secret_ids

    @staticmethod
    def _secret_id(server_id: str, kind: str, name: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.-") or "value"
        return f"mcp.{server_id}.{kind}.{safe_name}"

    def _sync_claude_agent_home(self, registry: Mapping[str, McpServerDefinition]) -> None:
        sync_claude_agent_home_mcp(
            agent_home=self._agent_home(),
            registry=registry,
            secret_resolver=self.secret_store.get_secret,
        )

    @staticmethod
    def _agent_home() -> Path:
        return Path(config.SYSTEM.AGENT_HOME)


mcp_management_service = McpManagementService()
