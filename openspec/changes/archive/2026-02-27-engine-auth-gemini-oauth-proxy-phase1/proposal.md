## Why

当前 `gemini` 仅支持 `cli_delegate` 鉴权链路（`--screen-reader` + PTY 编排），尚未具备 `oauth_proxy` 真代理能力。  
这导致 Gemini 与已支持协议代理的引擎（codex/opencode）在鉴权形态上不一致，并带来如下问题：

1. 依赖 TUI 文本锚点，流程稳定性受 CLI UI 变化影响；
2. 远程部署场景下，用户只能走编排链路，缺少更直接的 OAuth 代理入口；
3. 统一的 transport 语义未覆盖 Gemini（`oauth_proxy` 仍被拒绝）。

本 change 新增 `gemini + oauth_proxy + browser-oauth`，实现零 CLI/PTY 的协议代理链路，并保留现有 `cli_delegate` 链路不变。

## What Changes

1. 新增有效组合：
   - `engine=gemini`
   - `transport=oauth_proxy`
   - `auth_method=browser-oauth`
2. 新增 Gemini OAuth 代理 flow（PKCE + state + token exchange + 凭据写盘）。
3. 新增 Gemini 本地 callback listener（`/oauth2callback`），支持自动收口。
4. 保留手工 `/input(kind=text)` fallback，允许粘贴 redirect URL 或 code。
5. 管理页新增 Gemini OAuth 代理入口按钮，与 Gemini CLI 委托并行展示。
6. 明确本期非目标：不写入/不改写 `mcp-oauth-tokens-v2.json`。

## Scope

### In Scope

- `oauth_proxy` 增量支持 Gemini browser OAuth。
- 自动本地回调 + 手工输入 fallback 双路径。
- 会话状态机与审计字段对齐 `oauth_proxy` 语义。
- OpenSpec / 单测 / UI / 文档同步。

### Out of Scope

- `gemini + oauth_proxy + device-auth`。
- 修改现有 Gemini `cli_delegate` 编排行为。
- 改造 `auth-status` 判定逻辑。
- 读写 `mcp-oauth-tokens-v2.json`。

## Impact

主要改动文件：

- `server/services/engine_auth_flow_manager.py`
- `server/services/auth_runtime/orchestrators/oauth_proxy_orchestrator.py`
- `server/assets/templates/ui/engines.html`
- 新增 `server/services/gemini_oauth_proxy_flow.py`
- 新增 `server/services/gemini_local_callback_server.py`
- 相关单测与文档文件
