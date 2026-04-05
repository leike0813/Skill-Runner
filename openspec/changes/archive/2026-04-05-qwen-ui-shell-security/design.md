# Qwen UI Shell Security Design

## Design Overview

本设计为 Qwen UI shell 实现基于 session config 的安全限制，通过 JSON 配置层合并机制实现。

## Profile Contract

在 `adapter_profile.json` 的 `ui_shell` 块中配置：

```json
"ui_shell": {
  "command_id": "qwen-tui",
  "label": "Qwen TUI",
  "trust_bootstrap_parent": false,
  "sandbox_arg": null,
  "retry_without_sandbox_on_early_exit": false,
  "sandbox_probe_strategy": "static_unsupported",
  "sandbox_probe_message": "Qwen Code TUI runs without sandbox by default.",
  "auth_hint_strategy": "none",
  "runtime_override_strategy": "none",
  "config_assets": {
    "default_path": "../config/ui_shell_default.json",
    "enforced_path": "../config/ui_shell_enforced.json",
    "settings_schema_path": "../schemas/qwen_config_schema.json",
    "target_relpath": ".qwen/settings.json"
  }
}
```

## Session Config Layers

### ui_shell_default.json

```json
{
  "$schema": "../schemas/qwen_config_schema.json",
  "model": {
    "name": "coder-model"
  }
}
```

### ui_shell_enforced.json

```json
{
  "$schema": "../schemas/qwen_config_schema.json",
  "tools": {
    "sandbox": false,
    "approvalMode": "dontAsk"
  },
  "permissions": {
    "defaultMode": "dontAsk",
    "allow": [],
    "deny": [
      "Agent",
      "Bash",
      "Edit",
      "ExitPlanMode",
      "Glob",
      "Grep",
      "KillShell",
      "LSP",
      "NotebookEdit",
      "Read",
      "Skill",
      "TaskCreate",
      "TaskGet",
      "TaskList",
      "TaskOutput",
      "TaskStop",
      "TaskUpdate",
      "TodoWrite",
      "ToolSearch",
      "Write"
    ]
  },
  "sandbox": {
    "autoAllowBashIfSandboxed": false,
    "allowUnsandboxedCommands": false
  }
}
```

## Schema Extensions

在 `qwen_config_schema.json` 中添加：

```json
{
  "tools": {
    "type": "object",
    "properties": {
      "sandbox": { "type": "boolean" },
      "approvalMode": { 
        "type": "string",
        "enum": ["yolo", "default", "dontAsk", "autoEdit"]
      }
    }
  },
  "permissions": {
    "type": "object",
    "properties": {
      "defaultMode": {
        "type": "string",
        "enum": ["bypassPermissions", "dontAsk", "ask", "autoEdit"]
      },
      "allow": {
        "type": "array",
        "items": { "type": "string" }
      },
      "deny": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  },
  "sandbox": {
    "type": "object",
    "properties": {
      "autoAllowBashIfSandboxed": { "type": "boolean" },
      "allowUnsandboxedCommands": { "type": "boolean" }
    }
  }
}
```

## Implementation Details

### Config Target Path

UI shell 配置文件生成到：`<session_dir>/.qwen/settings.json`

这与 Qwen Code 的默认配置路径一致。

### Runtime Override Strategy

初始实现使用 `"none"` 策略，不添加动态配置。后续如需根据 sandbox 状态动态调整，可以添加 `_QwenUiShellRuntimeOverride` 类。

### Integration with Existing Flow

`ProfiledJsonSessionSecurity.prepare()` 方法会自动处理配置生成：
1. 加载 `default_layer`
2. 加载 `runtime_layer`（空）
3. 加载 `enforced_layer`
4. 使用 `config_generator.generate_config` 合并并验证
5. 写入目标路径

## Security Considerations

1. **enforced 配置优先级最高** - 通过 deep_merge 确保 enforced 配置不被覆盖
2. **默认拒绝模式** - `defaultMode: "dontAsk"` 确保未知操作被拒绝
3. **明确列出危险工具** - deny 列表包含所有可能修改系统状态的工具
