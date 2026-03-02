from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.engines.codex.auth import CodexOAuthProxyFlow
from server.engines.codex.auth.runtime_handler import CodexAuthRuntimeHandler
from server.engines.common.callbacks.openai_local_callback_server import openai_local_callback_server
from server.engines.common.openai_auth import OpenAIDeviceProxyFlow
from server.engines.gemini.auth import GeminiAuthCliFlow, GeminiOAuthProxyFlow
from server.engines.gemini.auth.callbacks.local_callback_server import gemini_local_callback_server
from server.engines.gemini.auth.runtime_handler import GeminiAuthRuntimeHandler
from server.engines.iflow.auth import IFlowAuthCliFlow, IFlowOAuthProxyFlow
from server.engines.iflow.auth.callbacks.local_callback_server import iflow_local_callback_server
from server.engines.iflow.auth.runtime_handler import IFlowAuthRuntimeHandler
from server.engines.opencode.auth import (
    OpencodeAuthCliFlow,
    OpencodeGoogleAntigravityOAuthProxyFlow,
    OpencodeOpenAIOAuthProxyFlow,
)
from server.engines.opencode.auth.callbacks.antigravity_local_callback_server import (
    antigravity_local_callback_server,
)
from server.engines.opencode.auth.runtime_handler import OpencodeAuthRuntimeHandler
from server.runtime.auth.callbacks import CallbackListenerRegistry
from server.runtime.auth.driver_registry import AuthDriverRegistry

_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_AUTH_METHOD_API_KEY = "api_key"


@dataclass(frozen=True)
class AuthBootstrapBundle:
    driver_registry: AuthDriverRegistry
    callback_listener_registry: CallbackListenerRegistry
    engine_auth_handlers: dict[str, Any]


def _register_auth_driver(
    registry: AuthDriverRegistry,
    *,
    transport: str,
    engine: str,
    auth_method: str,
    provider_id: str | None = None,
    start_method: str = "auth",
    execution_mode: str | None = None,
) -> None:
    registry.register(
        transport=transport,
        engine=engine,
        auth_method=auth_method,
        provider_id=provider_id,
        driver={
            "start_method": start_method,
            "execution_mode": execution_mode,
        },
    )


def _build_driver_registry() -> AuthDriverRegistry:
    registry = AuthDriverRegistry()
    # oauth_proxy
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="codex",
        auth_method=_AUTH_METHOD_CALLBACK,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="codex",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="gemini",
        auth_method=_AUTH_METHOD_CALLBACK,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="gemini",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="iflow",
        auth_method=_AUTH_METHOD_CALLBACK,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="iflow",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="opencode",
        auth_method=_AUTH_METHOD_CALLBACK,
        provider_id="openai",
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="opencode",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        provider_id="openai",
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="opencode",
        auth_method=_AUTH_METHOD_CALLBACK,
        provider_id="google",
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="opencode",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        provider_id="google",
        execution_mode="protocol_proxy",
    )
    _register_auth_driver(
        registry,
        transport="oauth_proxy",
        engine="opencode",
        auth_method=_AUTH_METHOD_API_KEY,
        execution_mode="protocol_proxy",
    )
    # cli_delegate
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="codex",
        auth_method=_AUTH_METHOD_CALLBACK,
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="codex",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="opencode",
        auth_method=_AUTH_METHOD_CALLBACK,
        provider_id="openai",
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="opencode",
        auth_method=_AUTH_METHOD_CALLBACK,
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="opencode",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        provider_id="openai",
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="gemini",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="iflow",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        start_method="iflow-cli-oauth",
        execution_mode="cli_delegate",
    )
    _register_auth_driver(
        registry,
        transport="cli_delegate",
        engine="opencode",
        auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        provider_id="google",
        execution_mode="cli_delegate",
    )
    return registry


def _build_callback_listener_registry() -> CallbackListenerRegistry:
    registry = CallbackListenerRegistry()
    registry.register(channel="openai", listener=openai_local_callback_server)
    registry.register(channel="gemini", listener=gemini_local_callback_server)
    registry.register(channel="iflow", listener=iflow_local_callback_server)
    registry.register(channel="antigravity", listener=antigravity_local_callback_server)
    return registry


def build_engine_auth_bootstrap(manager: Any, *, agent_home: Path) -> AuthBootstrapBundle:
    agent_home.mkdir(parents=True, exist_ok=True)
    # Flows are attached on manager because runtime handlers access them via manager attributes.
    manager._gemini_flow = GeminiAuthCliFlow()  # noqa: SLF001
    manager._gemini_oauth_proxy_flow = GeminiOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._iflow_oauth_proxy_flow = IFlowOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._iflow_flow = IFlowAuthCliFlow()  # noqa: SLF001
    manager._opencode_flow = OpencodeAuthCliFlow()  # noqa: SLF001
    manager._openai_device_proxy_flow = OpenAIDeviceProxyFlow()  # noqa: SLF001
    manager._codex_oauth_proxy_flow = CodexOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._opencode_openai_oauth_proxy_flow = OpencodeOpenAIOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._opencode_google_antigravity_oauth_proxy_flow = OpencodeGoogleAntigravityOAuthProxyFlow(  # noqa: SLF001
        agent_home
    )

    handlers = {
        "codex": CodexAuthRuntimeHandler(manager),
        "gemini": GeminiAuthRuntimeHandler(manager),
        "iflow": IFlowAuthRuntimeHandler(manager),
        "opencode": OpencodeAuthRuntimeHandler(manager),
    }
    return AuthBootstrapBundle(
        driver_registry=_build_driver_registry(),
        callback_listener_registry=_build_callback_listener_registry(),
        engine_auth_handlers=handlers,
    )
