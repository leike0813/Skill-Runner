## Context

当前 transport 分组接口已经稳定支持：

- `oauth_proxy`：codex、opencode(openai/google)
- `cli_delegate`：codex、gemini、iflow、opencode(provider)

Gemini 目前仅在 `cli_delegate` 可用。为了扩展统一抽象，需要新增一个协议代理 driver：`gemini_oauth_proxy`，并显式禁止该链路调用 CLI/PTY。

## Design Decisions

1. **零 CLI 原则**：`gemini + oauth_proxy` 只走协议代理，不启动 `gemini` 进程。
2. **双完成路径**：
   - 自动回调：会话生命周期内监听本地 `/oauth2callback`；
   - 手工兜底：用户可通过 `/input(kind=text)` 提交 redirect URL 或 code。
3. **状态机约束**：
   - `starting -> waiting_user -> code_submitted_waiting_result(可选) -> succeeded|failed|canceled|expired`
   - `oauth_proxy` 绝不出现 `waiting_orchestrator`。
4. **存储边界**：
   - 成功后写 `oauth_creds.json`（主鉴权文件）；
   - 可选同步 `google_accounts.json`；
   - 不触碰 `mcp-oauth-tokens-v2.json`（避免污染 MCP/API Key 通道）。
5. **兼容优先**：不改 Gemini `cli_delegate` 路径。

## Architecture

### 1) 新增 Flow：`gemini_oauth_proxy_flow.py`

职责：

1. 生成 PKCE（`code_verifier/code_challenge`）与 `state`；
2. 构造 Google authorize URL（Gemini CLI 同源 client/scope 语义）；
3. 解析用户输入（redirect URL 或 code）；
4. 调用 token endpoint 交换 token；
5. 可选拉取 userinfo(email)；
6. 原子写盘 `~/.gemini/oauth_creds.json`；
7. 可选更新 `~/.gemini/google_accounts.json`。

### 2) 新增 Listener：`gemini_local_callback_server.py`

职责：

1. 本地监听（默认 loopback，path=`/oauth2callback`）；
2. 将 `state/code/error` 回调给 manager；
3. 返回简洁成功/失败 HTML；
4. 生命周期与 auth session 绑定，不后台常驻。

### 3) Manager 接入：`engine_auth_flow_manager.py`

新增能力：

1. driver 注册：
   - `transport=oauth_proxy, engine=gemini, auth_method=browser-oauth`
2. start 分支：
   - 放行 Gemini oauth_proxy 组合；
   - 启动 Gemini 本地 listener；
   - 创建 flow runtime 并注册 state 映射；
   - 返回 `waiting_user + auth_url`。
3. refresh 分支：
   - 维护 `gemini_oauth_proxy` 状态推进；
   - TTL/终态收敛与清理。
4. input 分支：
   - Gemini oauth_proxy 允许 `kind=text|code`；
   - 提交后进入 `code_submitted_waiting_result`，完成后收敛终态。
5. finalize 分支：
   - 清理 state 映射与 callback listener。

### 4) Orchestrator/UI 适配

1. `oauth_proxy_orchestrator` 放行 `engine=gemini`，并映射到 `browser-oauth` method。
2. `engines.html` 新增 Gemini OAuth 代理按钮。
3. 输入提示文案按链路区分：
   - Gemini oauth_proxy：回调 URL / 授权码；
   - Gemini cli_delegate：授权码。

## Failure Handling

1. callback listener 启动失败：
   - 会话仍可启动；
   - 保持 `waiting_user`，仅手工 input 可用。
2. state 缺失/不匹配/重复消费：`failed`。
3. token exchange 失败：`failed` 并记录摘要。
4. 会话过期：`expired`。

## Observability

会话 `audit` 推荐字段：

1. `auto_callback_listener_started`
2. `auto_callback_success`
3. `manual_fallback_used`
4. `callback_mode` (`auto|manual`)

## Security

1. 不记录明文 code/token 到事件日志。
2. state 一次性消费，防重放。
3. listener 仅在 active session 存活期间开放。
