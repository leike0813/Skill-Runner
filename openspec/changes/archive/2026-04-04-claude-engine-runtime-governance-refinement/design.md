# claude-engine-runtime-governance-refinement Design

## Design Overview

本次 change 采用三条主线同时收口：

1. **命令最薄**：Claude 命令行只保留协议与会话骨架
2. **配置最厚**：模型、权限、sandbox 与 filesystem 约束全部收口到配置层
3. **UI shell 分治**：`ui_shell` 与 headless run/harness 使用不同的安全姿态

## Command Defaults

- `start` / `resume`：
  - `-p --output-format stream-json --verbose`
- `ui_shell`：
  - 空 launch args，表示交互模式不复用 headless 参数组

命令层不再承担：

- `--model`
- `--settings`
- 权限模式
- provider/token/base_url

## Configuration Layers

### Bootstrap

- 目标：`agent_home/.claude.json`
- 只初始化 Claude 全局状态
- 当前写入：`hasCompletedOnboarding = true`

### Runtime Settings

- 目标：`run_dir/.claude/settings.json`
- `default.json` 提供低风险默认值
- `enforced.json` 提供所有 run 必须成立的强约束

## Headless / Harness Policy

- `permissions.defaultMode = "bypassPermissions"`
- `sandbox.enabled = true`
- `sandbox.autoAllowBashIfSandboxed = true`
- `sandbox.allowUnsandboxedCommands = false`
- `includeGitInstructions = false`
- 动态 filesystem 规则围绕 `run_dir` 生成：
  - `allowWrite = [//<run_dir>]`
  - `denyWrite` / `denyRead` 覆盖 `agent_home` 与仓库根非 run 路径

## UI Shell Policy

- `ui_shell` 写 session-local `.claude/settings.json`
- 默认安全姿态：
  - `permissions.defaultMode = "dontAsk"`
  - 工具默认全禁用或接近全禁用
  - 网络保留
  - `sandbox.enabled = true`
  - `sandbox.allowUnsandboxedCommands = false`

## Schema Validation

Claude settings 校验切换为真实 JSON Schema 路径：

- 若 schema 是 JSON Schema，则用 `jsonschema` 进行校验
- 其他仍用旧的简化 schema 递归校验逻辑，保证现有 Gemini/iFlow 配置不回退

这样 Claude 可以正确识别 `env`、`permissions`、`sandbox`、`includeGitInstructions` 等字段。
