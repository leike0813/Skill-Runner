## MODIFIED Requirements

### Requirement: Auth runtime service chain MUST be observable and deterministic
系统 MUST 固化 auth runtime 调用链，并保证状态推进行为在重构后保持一致。

#### Scenario: start 采用标准服务链
- **WHEN** 新会话启动
- **THEN** 调用链为 `session_start_planner -> session_starter -> session_refresher`

#### Scenario: input 与 callback 采用独立服务
- **WHEN** 用户提交 input 或回调触发
- **THEN** 分别由 `session_input_handler` / `session_callback_completer` 收口
- **AND** 状态终态行为与重构前一致

### Requirement: oauth_proxy and cli_delegate state constraints MUST remain unchanged
重构后状态机约束 MUST 与既有语义一致。

#### Scenario: oauth_proxy 不出现 waiting_orchestrator
- **WHEN** `transport=oauth_proxy`
- **THEN** 会话状态不应进入 `waiting_orchestrator`

#### Scenario: cli_delegate 允许 waiting_orchestrator
- **WHEN** `transport=cli_delegate`
- **THEN** 会话可进入 `waiting_orchestrator`
