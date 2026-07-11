from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from server.engines.codebuddy.storage_layout import atomic_write_text, ensure_private_dir
from server.runtime.adapter.common.prompt_builder_common import render_run_execution_instructions
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.mcp import build_mcp_config_layer

if TYPE_CHECKING:
    from .execution_adapter import CodeBuddyExecutionAdapter


class CodeBuddyConfigComposer:
    _SETTINGS = {"autoUpdates": False, "disableAllHooks": True, "allowUntrustedFrontmatterHooks": False, "enableAllProjectMcpServers": False}

    def __init__(self, adapter: "CodeBuddyExecutionAdapter") -> None:
        self._adapter = adapter

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        workspace = ctx.run_dir / ".codebuddy"
        ensure_private_dir(workspace)
        settings = workspace / "settings.json"
        atomic_write_text(settings, json.dumps(self._SETTINGS, indent=2) + "\n")
        _resolution, mcp_config = build_mcp_config_layer(skill=ctx.skill, engine="codebuddy")
        atomic_write_text(workspace / "mcp.json", json.dumps(mcp_config, indent=2) + "\n")
        (ctx.run_dir / "CODEBUDDY.md").write_text(render_run_execution_instructions(run_dir=ctx.run_dir, profile=self._adapter.profile, skill=ctx.skill), encoding="utf-8")
        return settings
