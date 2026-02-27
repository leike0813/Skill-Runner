## Context

当前鉴权体系已按 transport 分组（`oauth_proxy` / `cli_delegate`），并支持：

- `codex` / `opencode(openai)` 的 OpenAI OAuth 代理；
- `gemini` / `iflow` / `opencode` provider 的 CLI 委托编排。

本设计在现有分层上新增一个独立 driver：`opencode_google_antigravity_oauth_proxy`，严格限定为协议代理，不复用 PTY 流程。

## Design Decisions

1. **零 CLI 原则**：`oauth_proxy + opencode + google` 不允许调用 CLI/PTY。
2. **双回调模式**：
   - 自动：session 生命周期内监听本地 `localhost:51121/oauth-callback`；
   - 手工：用户可通过 `/input(kind=text)` 提交完整 redirect URL 或 code。
3. **写盘复用**：自动与手工路径共享同一 token exchange + 持久化函数，避免分叉。
4. **账号文件策略**：`antigravity-accounts.json` 采用覆盖写入单账号 v4。
5. **兼容边界**：不调整现有 `cli_delegate` Google 清理/编排逻辑。
6. **凭据来源**：Google OAuth 客户端参数与插件同源常量硬编码，不做 env override。

## Architecture

### 1) 新增 Flow：`opencode_google_antigravity_oauth_proxy_flow.py`

职责：

1. 生成 PKCE（`verifier/challenge`）；
2. 生成 `state`（base64url(JSON)），至少含：
   - `verifier`
   - `projectId`（本期固定空串）
3. 构造 authorize URL（Google OAuth）；
4. 处理手工输入：
   - 提交完整 redirect URL：提取 `code/state`
   - 仅提交 `code`：使用会话 fallback state
5. token exchange（`https://oauth2.googleapis.com/token`）；
6. 拉取用户邮箱（userinfo）；
7. 输出规范化 token 结果给 auth store。

### 2) 新增 Listener：`antigravity_local_callback_server.py`

职责：

1. 启动临时 HTTP 监听（`127.0.0.1:51121`，path `/oauth-callback`）；
2. 回调命中后把 `state/code/error` 转发给 manager；
3. 返回简单成功/失败 HTML；
4. listener 随 session 启停，不后台常驻。

### 3) Manager 接入（`engine_auth_flow_manager.py`）

新增能力：

1. driver 矩阵注册新增：
   - `transport=oauth_proxy, engine=opencode, provider_id=google, auth_method=browser-oauth`
2. start 分支新增 Google oauth_proxy：
   - 创建 flow runtime；
   - 注册 state->session 映射；
   - 启动 antigravity listener；
   - 状态置 `waiting_user`，返回 `auth_url`。
3. callback 处理新增 `complete_google_antigravity_callback(...)`。
4. `input_session` 新增 Google oauth_proxy fallback 提交通道。
5. finalize 逻辑新增 Google listener stop + state 清理。
6. `oauth_proxy` Google 状态机约束：
   - `starting -> waiting_user -> (code_submitted_waiting_result) -> succeeded/failed/canceled/expired`
   - 不允许出现 `waiting_orchestrator`。

### 4) Auth Store 扩展（`opencode_auth_store.py`）

新增方法：

1. 覆盖写 `antigravity-accounts.json`（single-account v4）；
2. 从 refresh 串解析 token 主体与 `projectId`；
3. 更新 `activeIndex=0` 与 `activeIndexByFamily={claude:0, gemini:0}`。

`auth.json` 继续复用现有 `upsert_oauth(provider_id="google", ...)`。

## OAuth Parameters

与插件同源（硬编码）：

1. authorize endpoint: `https://accounts.google.com/o/oauth2/v2/auth`
2. token endpoint: `https://oauth2.googleapis.com/token`
3. redirect_uri: `http://localhost:51121/oauth-callback`
4. scopes:
   - `https://www.googleapis.com/auth/cloud-platform`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
   - `https://www.googleapis.com/auth/cclog`
   - `https://www.googleapis.com/auth/experimentsandconfigs`
5. `client_id/client_secret`：插件同款常量。

## Failure Handling

1. callback state 非法/重复/过期：`failed`。
2. token exchange 失败：`failed`，保留错误摘要。
3. listener 启动失败：不阻塞会话启动；会话仍可走手工 `/input` fallback。
4. 写盘失败：`failed`。

## Observability

会话 `audit` 增量建议：

1. `auto_callback_listener_started: bool`
2. `auto_callback_success: bool`
3. `manual_fallback_used: bool`
4. `callback_mode: "auto" | "manual"`

## Security

1. 不记录明文 code/token。
2. 回调 state 仅可消费一次。
3. listener 仅在活动 session 存活期间开放。
