## Why

当前 `iflow` 仅有 `cli_delegate` 鉴权链路，缺少与其他引擎一致的 `oauth_proxy` 真代理能力。  
这会导致：

1. 远程部署下只能依赖 TUI 编排；
2. 鉴权状态机语义在引擎之间不一致；
3. 无法在同一套 API/UI 中并列测试 `callback` 与 `auth_code_or_url` 两种 OAuth 模式。

参考 `references/iflow2api` 证据，可确认 iFlow OAuth 协议链路（authorize/token/user-info）与本地回调模式可实现，同时也可通过手工输入 code/URL 完成。

## What Changes

1. 新增 `iflow + oauth_proxy` 组合，支持：
   - `auth_method=callback`
   - `auth_method=auth_code_or_url`
2. `callback` 模式采用自动本地回调优先，同时保留 `/input` 手工兜底。
3. `auth_code_or_url` 模式不启本地 listener，仅通过 `/input` 手工完成。
4. 成功后以“实测兼容优先”写盘：
   - `.iflow/oauth_creds.json`
   - `.iflow/iflow_accounts.json`
   - `.iflow/settings.json`（至少保证 `selectedAuthType=oauth-iflow`、`baseUrl` 有效）
5. 保持 `iflow + cli_delegate` 原有行为不变。
6. 管理 UI 新增 `iFlow OAuth代理（Callback/AuthCode/URL）` 两个并列入口。

## Scope

### In Scope

- `iflow + oauth_proxy` 双模式；
- 本地 callback listener + 手工兜底；
- 会话状态机与审计字段对齐 `oauth_proxy` 语义；
- OpenSpec、后端、UI、测试、文档同步。

### Out of Scope

- iFlow device-auth；
- 修改 iFlow 现有 `cli_delegate` 编排逻辑；
- 修改 `auth-status` 判定规则（仅通过兼容写盘满足现有判定）。

## Impact

主要改动文件：

- 新增 `server/services/iflow_oauth_proxy_flow.py`
- 新增 `server/services/iflow_local_callback_server.py`
- 修改 `server/services/engine_auth_flow_manager.py`
- 修改 `server/services/auth_runtime/orchestrators/oauth_proxy_orchestrator.py`
- 修改 `server/assets/templates/ui/engines.html`
- 新增/更新相关单测与文档
