## Why

当前引擎鉴权虽然可用，但主要依赖内嵌 TUI 或手工复制凭据文件，前端可用性不足。  
在此前可行性研究中，`codex login --device-auth` 已被确认具备“后端发起、前端展示 challenge、用户外部完成授权”的实验基础。  
因此需要一个独立实现型 change，在不破坏现有 TUI/导入路径的前提下，先落地 Codex 单引擎 device-auth 代理闭环。

## What Changes

- 新增实验性 Codex device-auth 会话管理能力（仅 `codex`，仅 `device-auth`）。
- 新增 `/v1` 与 `/ui` 两组会话式接口：`start/status/cancel`。
- 在 Engine 管理页面新增“连接 Codex”入口与实时状态展示（URL/code/状态/取消）。
- 新增鉴权会话与内嵌 TUI 的全局互斥门控，避免并发交互冲突。
- 默认启用功能开关；支持通过环境变量关闭。
- 保持 `GET /v1/engines/auth-status` 语义不变，登录完成后 `codex.auth_ready` 与凭据文件状态一致。

## Capabilities

### New Capabilities

- `engine-auth-device-proxy-codex-phase1`: 提供 Codex device-auth 的会话化代理执行与前端可观测能力。

### Modified Capabilities

- `ui-engine-management`: 增加 Codex 连接入口与会话状态可视化。
- `engine-auth-observability`: 增加鉴权会话状态生命周期可观测语义。
- `management-api-surface`: 增加引擎鉴权会话 API 契约（`/v1/engines/auth/sessions*`）。

## Scope

### In Scope

- `codex` 引擎。
- `device-auth` 登录命令（`codex login --device-auth`）。
- 内存态会话 + TTL（默认 15 分钟）。
- 会话互斥冲突（与 UI TUI 共用一把全局门）。

### Out of Scope

- 非 codex 引擎 OAuth 代理实现。
- callback 端点与 token broker。
- API key 登录代理。
- 会话跨进程/跨重启恢复。

## Impact

- 变更集中在 `server/services`、`server/routers`、`server/models.py`、UI 模板与单元测试。
- 默认行为向前兼容：未使用新入口时，原 TUI 与凭据导入路径保持不变。
- 如出现问题，可通过 `ENGINE_AUTH_DEVICE_PROXY_ENABLED=0` 快速关闭实验功能。
