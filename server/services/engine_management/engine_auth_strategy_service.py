from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, Optional

import jsonschema  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]

from server.config_registry import keys
from server.config_registry.registry import config_registry


_VALID_TRANSPORTS = ("oauth_proxy", "cli_delegate")
_NON_OPENCODE_ENGINES = ("codex", "gemini", "iflow")
_ENGINE_KEYS = ("codex", "gemini", "iflow", "opencode")


class EngineAuthStrategyLoadError(RuntimeError):
    """Raised when engine auth strategy config cannot be loaded or validated."""


@dataclass(frozen=True)
class DriverStrategyEntry:
    transport: str
    engine: str
    auth_method: str
    provider_id: str | None
    start_method: str
    execution_mode: str


class EngineAuthStrategyService:
    def __init__(
        self,
        *,
        strategy_path: Path | None = None,
        schema_path: Path | None = None,
    ) -> None:
        self._strategy_path = strategy_path
        self._schema_path = schema_path
        self._lock = Lock()
        self._loaded = False
        self._payload: dict[str, Any] = {}

    def _load_schema(self) -> dict[str, Any]:
        schema_paths: tuple[Path, ...]
        if self._schema_path is not None:
            schema_paths = (self._schema_path,)
        else:
            schema_paths = config_registry.engine_auth_strategy_schema_paths()
        schema_path = next((path for path in schema_paths if path.exists()), None)
        if schema_path is None:
            joined = ", ".join(str(path) for path in schema_paths)
            raise EngineAuthStrategyLoadError(
                f"Failed to locate engine auth strategy schema. tried: {joined}"
            )
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EngineAuthStrategyLoadError(
                f"Failed to load engine auth strategy schema: {schema_path}"
            ) from exc
        if not isinstance(payload, dict):
            raise EngineAuthStrategyLoadError(
                f"Engine auth strategy schema must be an object: {schema_path}"
            )
        return payload

    def _load_strategy(self) -> dict[str, Any]:
        if self._strategy_path is not None:
            try:
                payload = yaml.safe_load(self._strategy_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise EngineAuthStrategyLoadError(
                    f"Failed to load engine auth strategy config: {self._strategy_path}"
                ) from exc
            if payload is None:
                return {}
            if not isinstance(payload, dict):
                raise EngineAuthStrategyLoadError(
                    f"Engine auth strategy config must be a mapping: {self._strategy_path}"
                )
            return payload

        aggregated: dict[str, Any] = {"version": 1, "engines": {}}
        for engine in _ENGINE_KEYS:
            strategy_path = config_registry.engine_config_path(
                engine=engine,
                filename=keys.ENGINE_AUTH_STRATEGY_NAME,
            )
            if not strategy_path.exists():
                raise EngineAuthStrategyLoadError(
                    f"Missing engine auth strategy file for `{engine}`: {strategy_path}"
                )
            try:
                engine_payload = yaml.safe_load(strategy_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise EngineAuthStrategyLoadError(
                    f"Failed to load engine auth strategy config: {strategy_path}"
                ) from exc
            if not isinstance(engine_payload, dict):
                raise EngineAuthStrategyLoadError(
                    f"Engine auth strategy config must be a mapping: {strategy_path}"
                )
            aggregated["engines"][engine] = engine_payload
        return aggregated

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        engines_obj = payload.get("engines")
        engines = engines_obj if isinstance(engines_obj, dict) else {}
        normalized_engines: dict[str, Any] = {}
        for engine_key, engine_value in engines.items():
            if not isinstance(engine_key, str) or not isinstance(engine_value, dict):
                continue
            normalized_engine_key = engine_key.strip().lower()
            normalized_engines[normalized_engine_key] = engine_value
        normalized_payload = dict(payload)
        normalized_payload["engines"] = normalized_engines
        return normalized_payload

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            schema = self._load_schema()
            payload = self._load_strategy()
            try:
                jsonschema.validate(instance=payload, schema=schema)
            except jsonschema.ValidationError as exc:
                raise EngineAuthStrategyLoadError(
                    f"Invalid engine auth strategy config: {self._strategy_path}: {exc.message}"
                ) from exc
            self._payload = self._normalize_payload(payload)
            self._loaded = True

    def reset_cache_for_testing(self) -> None:
        with self._lock:
            self._loaded = False
            self._payload = {}

    def _engine_block(self, engine: str) -> dict[str, Any]:
        self._ensure_loaded()
        normalized_engine = engine.strip().lower()
        engines_obj = self._payload.get("engines")
        engines = engines_obj if isinstance(engines_obj, dict) else {}
        block = engines.get(normalized_engine)
        return block if isinstance(block, dict) else {}

    def _opencode_provider_block(self, provider_id: str | None) -> dict[str, Any]:
        if not provider_id:
            return {}
        opencode = self._engine_block("opencode")
        providers_obj = opencode.get("providers")
        providers = providers_obj if isinstance(providers_obj, dict) else {}
        block = providers.get(provider_id.strip().lower())
        return block if isinstance(block, dict) else {}

    def _transport_block(
        self,
        *,
        engine: str,
        provider_id: str | None = None,
        transport: str,
    ) -> dict[str, Any]:
        normalized_transport = transport.strip().lower()
        if engine.strip().lower() == "opencode":
            provider_block = self._opencode_provider_block(provider_id)
            transports_obj = provider_block.get("transports")
        else:
            engine_block = self._engine_block(engine)
            transports_obj = engine_block.get("transports")
        transports = transports_obj if isinstance(transports_obj, dict) else {}
        block = transports.get(normalized_transport)
        return block if isinstance(block, dict) else {}

    def resolve_conversation_transport(self, engine: str, provider_id: str | None = None) -> str:
        normalized_engine = engine.strip().lower()
        if normalized_engine == "opencode":
            block = self._engine_block("opencode")
        else:
            block = self._engine_block(normalized_engine)
        in_conversation_obj = block.get("in_conversation")
        in_conversation = in_conversation_obj if isinstance(in_conversation_obj, dict) else {}
        transport_obj = in_conversation.get("transport")
        transport = transport_obj.strip().lower() if isinstance(transport_obj, str) else ""
        if transport in _VALID_TRANSPORTS:
            return transport
        # schema enforces a valid value, but keep a defensive fallback.
        return "oauth_proxy"

    def methods_for_conversation(self, engine: str, provider_id: str | None = None) -> tuple[str, ...]:
        normalized_engine = engine.strip().lower()
        if normalized_engine == "opencode":
            provider_block = self._opencode_provider_block(provider_id)
            in_conversation_obj = provider_block.get("in_conversation")
            in_conversation = in_conversation_obj if isinstance(in_conversation_obj, dict) else {}
        else:
            engine_block = self._engine_block(normalized_engine)
            in_conversation_obj = engine_block.get("in_conversation")
            in_conversation = in_conversation_obj if isinstance(in_conversation_obj, dict) else {}
        methods_obj = in_conversation.get("methods")
        methods = methods_obj if isinstance(methods_obj, list) else []
        normalized_methods: list[str] = []
        for method in methods:
            if isinstance(method, str):
                value = method.strip().lower()
                if value:
                    normalized_methods.append(value)
        return tuple(normalized_methods)

    def runtime_methods_for_transport(
        self,
        *,
        engine: str,
        transport: str,
        provider_id: str | None = None,
    ) -> tuple[str, ...]:
        block = self._transport_block(
            engine=engine,
            provider_id=provider_id,
            transport=transport,
        )
        methods_obj = block.get("methods")
        methods = methods_obj if isinstance(methods_obj, list) else []
        normalized: list[str] = []
        for method in methods:
            if isinstance(method, str):
                value = method.strip().lower()
                if value:
                    normalized.append(value)
        return tuple(normalized)

    def list_ui_capabilities(self) -> dict[str, dict[str, Any]]:
        payload: dict[str, dict[str, Any]] = {
            "oauth_proxy": {
                "codex": [],
                "gemini": [],
                "iflow": [],
                "opencode": {},
            },
            "cli_delegate": {
                "codex": [],
                "gemini": [],
                "iflow": [],
                "opencode": {},
            },
        }
        for engine in _NON_OPENCODE_ENGINES:
            for transport in _VALID_TRANSPORTS:
                payload[transport][engine] = list(
                    self.runtime_methods_for_transport(engine=engine, transport=transport)
                )

        opencode_block = self._engine_block("opencode")
        providers_obj = opencode_block.get("providers")
        providers = providers_obj if isinstance(providers_obj, dict) else {}
        for provider_id, provider_block in providers.items():
            if not isinstance(provider_id, str) or not isinstance(provider_block, dict):
                continue
            normalized_provider = provider_id.strip().lower()
            if not normalized_provider:
                continue
            for transport in _VALID_TRANSPORTS:
                methods = list(
                    self.runtime_methods_for_transport(
                        engine="opencode",
                        transport=transport,
                        provider_id=normalized_provider,
                    )
                )
                if methods:
                    payload[transport]["opencode"][normalized_provider] = methods
        return payload

    def iter_driver_entries(self) -> tuple[DriverStrategyEntry, ...]:
        entries: list[DriverStrategyEntry] = []

        for engine in _NON_OPENCODE_ENGINES:
            for transport in _VALID_TRANSPORTS:
                transport_block = self._transport_block(engine=engine, transport=transport)
                driver_obj = transport_block.get("driver")
                driver = driver_obj if isinstance(driver_obj, dict) else {}
                start_method = str(driver.get("start_method") or "").strip().lower()
                execution_mode = str(driver.get("execution_mode") or "").strip().lower()
                if not start_method or not execution_mode:
                    continue
                for method in self.runtime_methods_for_transport(engine=engine, transport=transport):
                    entries.append(
                        DriverStrategyEntry(
                            transport=transport,
                            engine=engine,
                            auth_method=method,
                            provider_id=None,
                            start_method=start_method,
                            execution_mode=execution_mode,
                        )
                    )

        opencode_block = self._engine_block("opencode")
        providers_obj = opencode_block.get("providers")
        providers = providers_obj if isinstance(providers_obj, dict) else {}
        for provider_id, provider_block in providers.items():
            if not isinstance(provider_id, str) or not isinstance(provider_block, dict):
                continue
            normalized_provider = provider_id.strip().lower()
            if not normalized_provider:
                continue
            for transport in _VALID_TRANSPORTS:
                transport_block = self._transport_block(
                    engine="opencode",
                    provider_id=normalized_provider,
                    transport=transport,
                )
                driver_obj = transport_block.get("driver")
                driver = driver_obj if isinstance(driver_obj, dict) else {}
                start_method = str(driver.get("start_method") or "").strip().lower()
                execution_mode = str(driver.get("execution_mode") or "").strip().lower()
                if not start_method or not execution_mode:
                    continue
                for method in self.runtime_methods_for_transport(
                    engine="opencode",
                    transport=transport,
                    provider_id=normalized_provider,
                ):
                    entries.append(
                        DriverStrategyEntry(
                            transport=transport,
                            engine="opencode",
                            auth_method=method,
                            provider_id=normalized_provider,
                            start_method=start_method,
                            execution_mode=execution_mode,
                        )
                    )

        entries.sort(
            key=lambda item: (
                item.transport,
                item.engine,
                item.provider_id or "",
                item.auth_method,
                item.start_method,
                item.execution_mode,
            )
        )
        return tuple(entries)

    def supports_start(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: Optional[str] = None,
    ) -> bool:
        normalized_transport = transport.strip().lower()
        normalized_engine = engine.strip().lower()
        normalized_method = auth_method.strip().lower()
        normalized_provider = (
            provider_id.strip().lower()
            if isinstance(provider_id, str) and provider_id.strip()
            else None
        )
        for entry in self.iter_driver_entries():
            if entry.transport != normalized_transport:
                continue
            if entry.engine != normalized_engine:
                continue
            if entry.auth_method != normalized_method:
                continue
            if entry.provider_id != normalized_provider:
                continue
            return True
        return False


engine_auth_strategy_service = EngineAuthStrategyService()
