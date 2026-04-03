# custom-provider-tui-launch-and-i18n Design

## Design Overview

本次 change 保持 custom provider 按 engine 隔离管理，并把 provider-row 级 TUI 启动限定在当前已选 engine 上。

- provider 行按钮不再选择 engine，只再选择 model
- 前端组合 `provider/model`
- 后端将 `custom_model` 透传到 `ui_shell_manager`
- 当前 provider-backed TUI 真实落地只做 `claude`

## UI Flow

在 `/ui/engines` 的 custom provider 表格中：

- 每行新增 `启动TUI`
- 仅当当前已选 engine 同时支持 custom provider 与 provider-backed TUI 时显示
- 点击后弹出轻量模型选择层
- 确认后调用现有 `/ui/engines/tui/session/start`

## Runtime Flow

- `POST /ui/engines/tui/session/start` 新增可选 `custom_model`
- `ui_shell_manager.start_session(..., custom_model=...)` 校验严格 `provider/model`
- 仅 `claude` 接受 `custom_model`
- Claude `ui_shell` session config 在 runtime override 中复用现有 custom provider 解析逻辑，把 `ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL` 写入 session-local settings

## Localization

为 custom provider 区补正式 locale key：

- provider CRUD 状态文案
- provider-row 启动 TUI
- 模型选择层标题、按钮、空模型/不支持/非法模型提示

