## ADDED Requirements

### Requirement: Snapshot auth_method MUST be normalized
系统 MUST 在会话快照中仅回显新语义 `auth_method`（`callback/auth_code_or_url/api_key`）。

#### Scenario: Snapshot never returns legacy auth_method
- **WHEN** 查询任意鉴权会话快照
- **THEN** `auth_method` 不返回历史值

### Requirement: waiting_orchestrator is cli_delegate-only
`waiting_orchestrator` MUST 仅用于 `cli_delegate`。

#### Scenario: oauth_proxy session state
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 状态机不出现 `waiting_orchestrator`

### Requirement: callback mode MUST support manual fallback input
当会话处于 `callback` 模式时，系统 MUST 允许手工 `/input` 作为远程部署兜底路径。

#### Scenario: Input accepted for callback mode fallback
- **WHEN** 会话 `auth_method=callback` 且调用 `/input`
- **THEN** 输入被接受并进入收口流程（`code_submitted_waiting_result` 或直接 `succeeded`）
