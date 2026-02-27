## Context

现有实现已具备 transport 分层（`oauth_proxy` / `cli_delegate`）和会话化 API，但 `auth_method` 存在历史值兼容逻辑。  
本次设计目标是“语义硬切换”：新语义单一来源，历史值全部拒绝。

## Design Decisions

1. **硬切换**：`auth_method` 仅允许 `callback/auth_code_or_url/api_key`，旧值直接 422。
2. **模式强分离**（仅 `oauth_proxy`）：
   - `callback`：自动回调优先链路，同时允许 `/input` 作为远程部署兜底；
   - `auth_code_or_url`：手工回填链路（通过 `/input`）。
3. **Gemini 双模式**：
   - `callback` 使用本地 listener（`localhost:51122`）；listener 启动失败即 `failed`；
   - `auth_code_or_url` 使用 `codeassist` 手工码流，不启动 listener。
4. **OpenCode Google 双模式**：
   - `callback` 使用 antigravity listener（`localhost:51121`）；listener 启动失败即 `failed`；
   - `auth_code_or_url` 手工输入 redirect URL/code，不启动 listener。
5. **CLI 委托保持行为**：仅更新字段语义映射，不改实际 CLI 编排路径。

## Matrix

### oauth_proxy

1. `codex`
   - `callback` -> OpenAI browser callback
   - `auth_code_or_url` -> OpenAI device/user-code
2. `opencode+openai`
   - `callback` -> OpenAI browser callback
   - `auth_code_or_url` -> OpenAI device/user-code
3. `gemini`
   - `callback` -> 自动回调
   - `auth_code_or_url` -> 手工码流
4. `opencode+google`
   - `callback` -> 自动回调
   - `auth_code_or_url` -> 手工回填

### cli_delegate

1. `codex`：`callback`/`auth_code_or_url`
2. `opencode+openai`：`callback`/`auth_code_or_url`
3. `gemini`：仅 `auth_code_or_url`
4. `opencode+google`：仅 `auth_code_or_url`
5. `iflow`：仅 `auth_code_or_url`（语义迁移，仍走既有 CLI）

## Failure Handling

1. 旧值请求：`422 unsupported auth_method`。
2. callback 模式 listener 不可用：`failed`（不降级到手工输入）。
3. callback 模式调用 `/input`：允许并按手工兜底路径处理。

## Observability

1. `snapshot.auth_method` 仅返回新语义值。
2. `waiting_orchestrator` 仅允许出现在 `cli_delegate`。
3. `audit.callback_mode` 记录实际收口方式：
   - auto：通过本地 listener 自动回调收口；
   - manual：通过 `/input` 手工回填收口（包括 callback 模式兜底）。
