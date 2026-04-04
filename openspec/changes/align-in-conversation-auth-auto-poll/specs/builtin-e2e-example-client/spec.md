## MODIFIED Requirements

### Requirement: 示例客户端 MUST 支持交互式对话直到终态

The example client MUST present a product-style chat experience while preserving FCMP waiting_auth semantics, including inputless auth challenges.

#### Scenario: waiting_auth auto-poll hides reply composer

- **GIVEN** 客户端收到 `pending_auth.accepts_chat_input=false`
- **AND** payload 仍包含 `auth_url` 或 `user_code`
- **WHEN** Observation 页面渲染 waiting_auth 卡片
- **THEN** 客户端 MUST 隐藏回复输入框
- **AND** MUST 继续显示 auth 链接 / user code
- **AND** MUST 等待后台状态轮询推进会话
