## Why

当前引擎鉴权中的 `auth_method` 仍混用历史值（`browser-oauth/device-auth/...`）与新值，导致：

1. API 契约不稳定，前后端语义漂移；
2. `gemini` 与 `opencode+google(antigravity)` 在 `oauth_proxy` 下缺少互补模式；
3. 测试阶段矩阵入口不完整，难以做对照验证。

本 change 统一 `auth_method` 为新语义，并在不改变 `cli_delegate` 编排行为的前提下，为 `gemini` 与 `opencode+google` 的 `oauth_proxy` 补齐双模式。

## What Changes

1. `auth_method` 统一为：
   - `callback`
   - `auth_code_or_url`
   - `api_key`
2. 旧值立即废弃并返回 422：
   - `browser-oauth`
   - `device-auth`
   - `screen-reader-google-oauth`
   - `iflow-cli-oauth`
   - `opencode-provider-auth`
3. `oauth_proxy` 新增/收敛行为：
   - `gemini` 支持 `callback` 与 `auth_code_or_url` 双模式；
   - `opencode+provider_id=google` 支持 `callback` 与 `auth_code_or_url` 双模式。
4. `cli_delegate` 不新增能力，仅把鉴权方式字段迁移到新语义：
   - `codex`：`callback` / `auth_code_or_url`
   - `opencode+openai`：`callback` / `auth_code_or_url`
   - `gemini`：仅 `auth_code_or_url`
   - `opencode+google`：仅 `auth_code_or_url`
5. 管理 UI 保留并列按钮（测试阶段不自动切换），统一发新语义。

## Scope

### In Scope

- `codex`、`opencode+openai`、`gemini`、`opencode+google(antigravity)`；
- `oauth_proxy` 与 `cli_delegate` 的 auth_method 语义统一；
- 相关 API/UI/测试/文档同步。

### Out of Scope

- 新 provider 扩展；
- 自动策略切换；
- 运行时新的 transport 引入。

## Impact

- 公共请求参数约束改变（旧值不再兼容）；
- 管理 UI 鉴权按钮与文案更新；
- 路由/编排器/会话状态回显的 `auth_method` 值统一。
