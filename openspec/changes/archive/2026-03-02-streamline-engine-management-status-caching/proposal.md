## Why

当前 engine 管理页把版本探测、auth 文件存在性探测和 sandbox 摘要混在同一个列表里，语义不准确，且页面读路径会触发 CLI 探测，导致首屏延迟和缓存来源不一致。现在需要把 engine 列表收敛为“后台刷新后的稳定缓存视图”，避免误导性状态字段继续暴露给 UI 和 management API。

## What Changes

- 移除 engine 管理域的 auth 状态探测能力，不再在 management API、UI 表格和公开 `/v1/engines/auth-status` 接口中暴露该摘要。
- 移除 engine 管理表格中的 sandbox 列；sandbox 状态仅保留在内置 shell banner 与对应 TUI 会话响应中。
- 新增 engine 版本缓存服务，统一读写 `data/agent_status.json`，并限定版本探测触发时机为 startup、升级成功后和每日后台刷新。
- 调整 management API 与 UI 读路径为“只读缓存”，不再在页面访问时触发 CLI 版本探测。
- 将 `/ui/engines` 改为服务端直出表格，移除首屏 HTMX 延迟加载和“正在检测”提示。

## Capabilities

### New Capabilities
- `engine-status-cache-management`: 约束 engine 版本缓存的持久化、触发时机和读路径降级行为。

### Modified Capabilities
- `management-api-surface`: 收缩 engine 管理摘要/详情字段，移除 auth probe 与 sandbox probe 摘要。
- `web-management-ui`: 调整 engine 管理页为 SSR 直接渲染，并移除 auth/sandbox 列与首屏延迟探测。
- `ui-engine-inline-terminal`: 明确 sandbox 信息仅在内嵌终端 banner 中展示，不再在 engine 列表摘要中复用。

## Impact

- 影响代码主要位于 `server/services/engine_management/*`、`server/routers/management.py`、`server/routers/engines.py`、`server/routers/ui.py`、UI 模板和相关测试。
- `GET /v1/management/engines*` 的内部响应字段会收缩，`GET /v1/engines/auth-status` 将下线。
- 不新增外部依赖；继续沿用 `data/agent_status.json` 作为 engine 版本缓存 SSOT。
