## ADDED Requirements

### Requirement: OpenCode Google oauth_proxy 会话 MUST 遵循 oauth_proxy 状态机语义
系统 MUST 保障该链路不会进入 `waiting_orchestrator`。

#### Scenario: 正常等待授权
- **WHEN** 会话已生成 auth URL 并等待用户完成浏览器授权
- **THEN** 状态为 `waiting_user`

#### Scenario: 手工输入已提交
- **WHEN** 用户通过 input 提交 URL/code 且已被接受
- **THEN** 状态为 `code_submitted_waiting_result` 或直接 `succeeded`

#### Scenario: 禁止 CLI 专属状态
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 快照中不应出现 `waiting_orchestrator`

### Requirement: 自动回调与手工兜底 MUST 可审计
系统 MUST 在会话审计字段中记录回调方式与结果。

#### Scenario: 自动回调成功
- **WHEN** listener 成功接收并完成回调
- **THEN** `audit.auto_callback_listener_started=true`
- **AND** `audit.auto_callback_success=true`
- **AND** `audit.callback_mode="auto"`

#### Scenario: 手工 fallback 成功
- **WHEN** 用户通过 input 完成流程
- **THEN** `audit.manual_fallback_used=true`
- **AND** `audit.callback_mode="manual"`

### Requirement: 单账号覆盖写盘结果 MUST 可观察
系统 MUST 在会话审计字段记录 Google 单账号覆盖写盘结果摘要。

#### Scenario: 覆盖写盘成功
- **WHEN** token exchange 完成并写盘
- **THEN** 审计中包含账号覆盖成功标记（如 `audit.google_antigravity_single_account_written=true`）
