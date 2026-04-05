## Design Summary

会话内鉴权继续复用现有 engine auth session 生命周期，不新增新的 run-side auth 状态机。  
本轮只调整会话层对 runtime auth session 的解释方式：

- `RunAuthOrchestrationService` 以策略声明的 `in_conversation.transport` 启动会话；
- `PendingAuth` 的 `accepts_chat_input` / `input_kind` / prompt / instructions 同时取决于：
  - 选中的 conversation auth method；
  - runtime snapshot 中的 `input_kind`；
  - transport 的 `session_behavior`；
- 对 `qwen-oauth + oauth_proxy`，`session_behavior(input_required=false,polling_start=immediate)` 直接驱动无输入 auto-poll；
- 会话协议中原先专门的 `authorization_code` 语义被 `auth_code_or_url` 取代，客户端统一提交这一种类。

## Key Decisions

### 会话协议直接切新

不保留 `authorization_code` 的读旧写新兼容：

- `AuthMethod.AUTH_CODE_OR_URL`
- `AuthChallengeKind.AUTH_CODE_OR_URL`
- `AuthSubmissionKind.AUTH_CODE_OR_URL`

所有运行时事件、schema、客户端默认值和测试一起切换，避免长期双语义并存。

### Auto-poll 仍留在声明式框架内

共享生命周期不新增 qwen 特判。  
是否需要聊天输入，完全由策略层 `session_behavior` 控制；会话编排只负责消费该声明并生成正确的 `PendingAuth` 读模型。

### 会话 transport 与策略对齐

会话编排不再硬编码 `oauth_proxy`，而是读取策略中的 `in_conversation.transport`。  
这样 provider-aware engine 与普通 engine 在会话中遵循同一声明式入口。
