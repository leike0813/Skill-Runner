## Why

此前 `qwen-oauth + oauth_proxy` 已在 engine 管理侧支持声明式 auto-poll，但会话中的 `waiting_auth` 仍沿用旧的 challenge 画像逻辑：

1. 会话编排不会消费 `session_behavior`，导致 qwen 仍表现为“需要聊天输入任意文本后才继续”；
2. 管理 UI 使用 `auth_code_or_url`，会话协议却仍输出 `authorization_code`，前后端语义分裂；
3. E2E 示例客户端、runtime schema 与 FCMP auth payload 没有同步到新语义。

## What Changes

1. 会话编排改为消费策略声明的 `in_conversation.transport` 与 `session_behavior`；
2. 会话 auth method / challenge kind / submission kind 统一切到 `auth_code_or_url`；
3. `qwen-oauth + oauth_proxy` 在 `waiting_auth` 中隐藏输入框并立即后台轮询；
4. 新增独立 change 记录本轮 breaking protocol 变化。

## Scope

### In Scope

- `waiting_auth` 会话编排与 `PendingAuth` 载荷；
- 会话 auth 相关枚举、runtime schema、FCMP auth input accepted payload；
- E2E 示例客户端 waiting_auth 输入协议；
- 与上述行为相关的 OpenSpec delta specs。

### Out of Scope

- engine 管理侧 auth session 路由或 UI 新增；
- 其他 provider/transport 的行为重设计；
- 兼容保留 `authorization_code` 旧值。
