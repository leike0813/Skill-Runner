from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.engines.claude.auth import ClaudeAuthCliFlow, ClaudeOAuthProxyFlow
from server.engines.claude.auth.callbacks.local_callback_server import (
    claude_local_callback_server,
)
from server.engines.claude.auth.runtime_handler import ClaudeAuthRuntimeHandler
from server.engines.codex.auth import CodexOAuthProxyFlow
from server.engines.codex.auth.runtime_handler import CodexAuthRuntimeHandler
from server.engines.common.callbacks.openai_local_callback_server import (
    openai_local_callback_server,
)
from server.engines.common.openai_auth import OpenAIDeviceProxyFlow
from server.engines.gemini.auth import GeminiAuthCliFlow, GeminiOAuthProxyFlow
from server.engines.gemini.auth.callbacks.local_callback_server import (
    gemini_local_callback_server,
)
from server.engines.gemini.auth.runtime_handler import GeminiAuthRuntimeHandler
from server.engines.opencode.auth import (
    OpencodeAuthCliFlow,
    OpencodeGoogleAntigravityOAuthProxyFlow,
    OpencodeOpenAIOAuthProxyFlow,
)
from server.engines.opencode.auth.callbacks.antigravity_local_callback_server import (
    antigravity_local_callback_server,
)
from server.engines.opencode.auth.runtime_handler import OpencodeAuthRuntimeHandler
from server.engines.qwen.auth import (
    QwenAuthCliFlow,
    CodingPlanAuthFlow,
    QwenOAuthProxyFlow,
)
from server.engines.qwen.auth.runtime_handler import QwenAuthRuntimeHandler
from server.runtime.auth.callbacks import CallbackListenerRegistry
from server.runtime.auth.cli_pty_runtime import detect_pywinpty_support
from server.runtime.auth.driver_registry import AuthDriverRegistry
from server.services.engine_management.engine_auth_strategy_service import (
    engine_auth_strategy_service,
)

logger = logging.getLogger(__name__)
_WINDOWS_PYWINPTY_ENGINES = frozenset({"gemini", "opencode", "qwen"})


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


def _build_driver_registry(
    *, disabled_cli_delegate_engines: set[str] | None = None
) -> AuthDriverRegistry:
    disabled = disabled_cli_delegate_engines or set()
    registry = AuthDriverRegistry()
    for entry in engine_auth_strategy_service.iter_driver_entries():
        if entry.transport == "cli_delegate" and entry.engine in disabled:
            continue
        _register_auth_driver(
            registry,
            transport=entry.transport,
            engine=entry.engine,
            auth_method=entry.auth_method,
            provider_id=entry.provider_id,
            start_method=entry.start_method,
            execution_mode=entry.execution_mode,
        )
    return registry


def _resolve_disabled_cli_delegate_engines() -> set[str]:
    if not platform.system().lower().startswith("win"):
        return set()
    available, detail = detect_pywinpty_support()
    if available:
        return set()
    disabled = set(_WINDOWS_PYWINPTY_ENGINES)
    reason = detail or "unknown_reason"
    logger.warning(
        "pywinpty is unavailable on Windows; disabling cli_delegate for engines=%s reason=%s fix=install_pywinpty_in_runtime_env",
        ",".join(sorted(disabled)),
        reason,
    )
    return disabled


def _build_callback_listener_registry() -> CallbackListenerRegistry:
    registry = CallbackListenerRegistry()
    registry.register(channel="openai", listener=openai_local_callback_server)
    registry.register(channel="gemini", listener=gemini_local_callback_server)
    registry.register(channel="antigravity", listener=antigravity_local_callback_server)
    registry.register(channel="claude", listener=claude_local_callback_server)
    return registry


def build_engine_auth_bootstrap(
    manager: Any, *, agent_home: Path
) -> AuthBootstrapBundle:
    agent_home.mkdir(parents=True, exist_ok=True)
    disabled_cli_delegate_engines = _resolve_disabled_cli_delegate_engines()
    # Flows are attached on manager because runtime handlers access them via manager attributes.
    manager._gemini_flow = GeminiAuthCliFlow()  # noqa: SLF001
    manager._gemini_oauth_proxy_flow = GeminiOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._opencode_flow = OpencodeAuthCliFlow()  # noqa: SLF001
    manager._claude_flow = ClaudeAuthCliFlow()  # noqa: SLF001
    manager._openai_device_proxy_flow = OpenAIDeviceProxyFlow()  # noqa: SLF001
    manager._codex_oauth_proxy_flow = CodexOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._claude_oauth_proxy_flow = ClaudeOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._opencode_openai_oauth_proxy_flow = OpencodeOpenAIOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._opencode_google_antigravity_oauth_proxy_flow = (
        OpencodeGoogleAntigravityOAuthProxyFlow(  # noqa: SLF001
            agent_home
        )
    )
    manager._qwen_oauth_proxy_flow = QwenOAuthProxyFlow(agent_home)  # noqa: SLF001
    manager._qwen_coding_plan_flow = CodingPlanAuthFlow(agent_home)  # noqa: SLF001
    manager._qwen_flow = QwenAuthCliFlow(agent_home)  # noqa: SLF001

    handlers = {
        "codex": CodexAuthRuntimeHandler(manager),
        "gemini": GeminiAuthRuntimeHandler(manager),
        "opencode": OpencodeAuthRuntimeHandler(manager),
        "claude": ClaudeAuthRuntimeHandler(manager),
        "qwen": QwenAuthRuntimeHandler(manager),
    }
    return AuthBootstrapBundle(
        driver_registry=_build_driver_registry(
            disabled_cli_delegate_engines=disabled_cli_delegate_engines
        ),
        callback_listener_registry=_build_callback_listener_registry(),
        engine_auth_handlers=handlers,
    )
