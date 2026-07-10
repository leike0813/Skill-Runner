from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

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
        workspace.mkdir(parents=True, exist_ok=True)
        settings = workspace / "settings.json"
        settings.write_text(json.dumps(self._SETTINGS, indent=2) + "\n", encoding="utf-8")
        _resolution, mcp_config = build_mcp_config_layer(skill=ctx.skill, engine="codebuddy")
        (workspace / "mcp.json").write_text(json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
        (ctx.run_dir / "CODEBUDDY.md").write_text(render_run_execution_instructions(run_dir=ctx.run_dir, profile=self._adapter.profile, skill=ctx.skill), encoding="utf-8")
        skills_root = workspace / "skills"
        skills_root.mkdir(exist_ok=True)
        if ctx.skill.path is not None:
            target = skills_root / ctx.skill.id
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(ctx.skill.path, target)
        return settings
