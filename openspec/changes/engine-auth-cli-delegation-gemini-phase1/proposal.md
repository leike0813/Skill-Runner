## Why

当前实验能力仅覆盖 Codex device-auth。Gemini 已具备 `--screen-reader` 可解析 TUI 输出，能够在后端通过 PTY 驱动实现“CLI 委托编排鉴权”，显著降低用户使用门槛。  
同时，本期必须保持与既有鉴权观测链路解耦：Gemini 委托编排会话成功与否只看 CLI 输出锚点，不依赖 auth 文件与 `auth-status` 判定逻辑。

## What Changes

- 新增 Gemini 鉴权 driver：`gemini --screen-reader` + PTY I/O 编排。
- 复用现有 `/v1` 与 `/ui` 会话 API，新增 `submit` 动作用于提交 authorization code。
- 若启动时已在主界面，自动发送 `/auth login` 强制重走 Google OAuth。
- 会话成功判定仅基于 Gemini CLI 输出锚点，不读取 auth 文件。
- 保留 Codex 现有 device-auth 行为，不改 `GET /v1/engines/auth-status` 逻辑。

## Capabilities

### New Capabilities

- `engine-auth-cli-delegation-gemini-phase1`: Gemini screen-reader CLI 委托编排鉴权（Phase 1）。

### Modified Capabilities

- `management-api-surface`: 鉴权会话接口新增 submit 子动作。
- `ui-engine-management`: Engine 管理页新增 Gemini 连接与授权码提交交互。
- `engine-auth-observability`: 鉴权会话状态机扩展 Gemini 专用状态并定义“输出锚点判定”语义。

## Scope

### In Scope

- 引擎：`gemini`。
- 方法：`screen-reader-google-oauth`（仅 Login with Google 自动流）。
- 会话接口：`start/status/cancel/submit`。
- 互斥门控：与内嵌 TUI 维持全局互斥。

### Out of Scope

- Gemini API Key / Vertex 自动化。
- ttyd 会话链路复用。
- 回调式 OAuth。
- 修改 `auth-status` 实现或语义。

## Impact

- 主要影响 `server/services`、`server/routers`、`server/models.py`、`server/assets/templates/ui` 与对应单测。
- 对现有调用兼容：`start/status/cancel` 不破坏；Codex 行为保持不变。
