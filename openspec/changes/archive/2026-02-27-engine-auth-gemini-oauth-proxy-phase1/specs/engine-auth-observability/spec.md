## ADDED Requirements

### Requirement: Gemini oauth_proxy 会话 MUST 遵循 oauth_proxy 状态机语义
系统 MUST 确保该链路不出现 CLI 专属状态 `waiting_orchestrator`。

#### Scenario: 正常等待授权
- **WHEN** 会话已生成授权 URL 并等待用户授权
- **THEN** 状态为 `waiting_user`

#### Scenario: 手工输入已提交
- **WHEN** 用户通过 input 提交 URL/code 且已被接受
- **THEN** 状态为 `code_submitted_waiting_result` 或直接 `succeeded`

#### Scenario: 禁止 CLI 专属状态
- **WHEN** 会话 `transport=oauth_proxy` 且 `engine=gemini`
- **THEN** 快照状态不应为 `waiting_orchestrator`

### Requirement: Gemini oauth_proxy 回调模式 MUST 可审计
系统 MUST 在会话审计字段中记录自动回调与手工 fallback 的路径信息。

#### Scenario: 自动回调成功
- **WHEN** listener 成功接收回调并完成 token exchange
- **THEN** `audit.auto_callback_listener_started=true`
- **AND** `audit.auto_callback_success=true`
- **AND** `audit.callback_mode="auto"`

#### Scenario: 手工 fallback 成功
- **WHEN** 用户通过 input 完成流程
- **THEN** `audit.manual_fallback_used=true`
- **AND** `audit.callback_mode="manual"`

### Requirement: Gemini oauth_proxy 本期 MUST 不改写 MCP token 文件
系统 MUST 不在该链路写入 `mcp-oauth-tokens-v2.json`。

#### Scenario: 鉴权成功后的文件副作用
- **WHEN** Gemini oauth_proxy 会话成功
- **THEN** 主鉴权文件（`oauth_creds.json`）被写入/更新
- **AND** `mcp-oauth-tokens-v2.json` 保持不变
