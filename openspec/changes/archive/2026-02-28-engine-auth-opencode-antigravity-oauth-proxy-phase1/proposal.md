## Why

当前 `opencode + provider_id=google` 仅支持 `cli_delegate` 鉴权路径，流程依赖 PTY 编排与菜单驱动。  
这条路径可用，但存在以下问题：

1. 对终端输出格式敏感，稳定性依赖 CLI UI 细节；
2. 回调链路不统一，远程场景常需要用户额外操作；
3. 无法与既有 `oauth_proxy` 协议代理策略保持一致。

本 change 在不影响现有 `cli_delegate` Google 路径的前提下，新增 `oauth_proxy` 真代理能力，满足“零 CLI/PTY + 自动本地回调 + 手工输入兜底”。

## What Changes

1. 新增 `opencode + google + oauth_proxy + browser-oauth` 组合支持。
2. 新增 Antigravity Google OAuth 协议流（PKCE + state + token exchange），不调用 CLI 进程。
3. 新增本地回调 listener（`http://localhost:51121/oauth-callback`）：
   - 会话启动后自动监听；
   - 回调成功后自动收口；
   - 与手工 `/input(kind=text)` 共享同一 exchange/写盘函数。
4. 成功写盘：
   - `~/.local/share/opencode/auth.json` 的 `google` oauth 项；
   - `~/.config/opencode/antigravity-accounts.json` 覆盖为单账号 v4。
5. 管理页新增 OpenCode Google OAuth 代理独立按钮。
6. 明确不改现有 `cli_delegate` Google 流程与行为。

## Scope

### In Scope

- `oauth_proxy` 增量支持 `opencode/google/browser-oauth`。
- 自动回调与手工输入 fallback 双路径并行可用。
- 单账号覆盖写盘策略。
- OpenSpec + 文档 + 单测/路由测增量覆盖。

### Out of Scope

- Google `oauth_proxy + device-auth`。
- 其他 provider 的 oauth_proxy 增量扩展。
- `cli_delegate` Google 链路行为重构。

## Impact

- 主要代码变更：
  - `server/services/engine_auth_flow_manager.py`
  - `server/services/opencode_auth_store.py`
  - 新增 Google OAuth proxy flow 与本地 callback server
  - `server/assets/templates/ui/engines.html`
  - `server/assets/templates/ui/partials/engines_table.html`
  - 相关路由/模型/测试与文档
- 对外 API 不新增端点，仅放行新的有效 start 组合。
