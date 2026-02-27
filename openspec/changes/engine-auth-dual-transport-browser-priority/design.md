## Context

当前 `EngineAuthFlowManager` 已支持 `transport`，但缺少“鉴权方式”一级显式契约。  
本次改造新增 `auth_method` 维度，用于稳定实现 OpenAI 2x2 矩阵：

1. `oauth_proxy + browser-oauth`
2. `oauth_proxy + device-auth`
3. `cli_delegate + browser-oauth`
4. `cli_delegate + device-auth`

适用引擎仅 `codex` 与 `opencode(provider_id=openai)`。

## Target Architecture

### 1) Session Contract

新增字段：
1. `start.auth_method?: "browser-oauth" | "device-auth" | "api_key"`
2. `snapshot.auth_method?: string`

兼容策略：
1. `method` 字段继续保留（不破坏旧客户端）。
2. 若 `auth_method` 缺失，按引擎默认推导：
   - `codex`: `browser-oauth`
   - `opencode/openai`: `browser-oauth`
   - `opencode/api_key provider`: `api_key`

### 2) Dispatch Matrix

分发键升级为 `(engine, transport, method, provider_id, auth_method)`，并显式拒绝非法组合（422）。

#### Codex

1. `oauth_proxy + browser-oauth` => `CodexOAuthProxyFlow`（协议代理）
2. `oauth_proxy + device-auth` => `OpenAIDeviceProxyFlow + Codex write`
3. `cli_delegate + browser-oauth` => `codex login`
4. `cli_delegate + device-auth` => `codex login --device-auth`

#### OpenCode/OpenAI

1. `oauth_proxy + browser-oauth` => `OpencodeOpenAIOAuthProxyFlow`（协议代理）
2. `oauth_proxy + device-auth` => `OpenAIDeviceProxyFlow + Opencode write`
3. `cli_delegate + browser-oauth` => `opencode auth login` + 菜单选 `ChatGPT (browser)`
4. `cli_delegate + device-auth` => `opencode auth login` + 菜单选 `ChatGPT Pro/Plus (headless)`

### 3) OAuth Proxy Flows

#### Browser OAuth (existing, retained)

状态机：
1. `starting`
2. `waiting_user`
3. callback success -> `succeeded`
4. callback unavailable -> `waiting_user` + `/input` fallback
5. `/input` 提交 -> `code_submitted_waiting_result` -> `succeeded|failed`

#### Device Auth (new protocol proxy)

状态机：
1. `starting`
2. `waiting_user`（返回 `verification_url + user_code`）
3. 后端按 `interval` 轮询 `/api/accounts/deviceauth/token`
4. 轮询成功后换取 token 并写盘 -> `succeeded`
5. 超时/错误 -> `failed|expired`

约束：
1. `oauth_proxy + device-auth` 禁止 CLI/PTY/subprocess。
2. `waiting_orchestrator` 禁止出现在 `oauth_proxy`。

### 4) Callback & Fallback

browser OAuth 回调端点继续使用：
1. `GET /v1/engines/auth/callback/openai`（免 Basic Auth）
2. 本地 `OpenAILocalCallbackServer` 动态启停（会话级）

安全要求：
1. `state` 与 session 绑定
2. TTL 校验
3. 一次性消费防重放

fallback：
1. 支持粘贴 redirect URL（带 `code`）
2. 支持粘贴裸 `code`

### 5) UI Model

管理页新增测试矩阵按钮（仅 codex/openai）：
1. OAuth代理 + browser-oauth
2. OAuth代理 + device-auth
3. CLI委托 + browser-oauth
4. CLI委托 + device-auth

展示规则：
1. `waiting_orchestrator` 仅用于 CLI 自动操作阶段。
2. `auth_input` 是否展示由 `input_kind` 驱动，避免 device 模式误显示输入框。
3. 输入提示按 `engine + transport + auth_method` 定制。

## Failure Modes

1. 矩阵组合非法 -> 422
2. device-auth usercode 获取失败 -> failed
3. device-auth 轮询超时/错误 -> failed/expired
4. callback state 无效/过期/重放 -> 400 并拒绝写盘
5. CLI 退出但 auth 未就绪 -> failed

## Compatibility

1. gemini/iflow 仍仅支持 `cli_delegate`。
2. opencode 非 openai provider 维持既有行为。
3. 旧客户端仅传 `method` 不传 `auth_method` 继续可用（按默认推导）。
