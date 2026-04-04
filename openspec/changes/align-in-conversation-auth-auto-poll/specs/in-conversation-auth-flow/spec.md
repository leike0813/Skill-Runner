## MODIFIED Requirements

### Requirement: Auth challenge MUST be surfaced inside the chat session

系统 MUST 在聊天窗口内向用户呈现 auth prompt、链接和输入要求，并允许无输入 challenge 通过声明式策略自动推进。

#### Scenario: qwen oauth_proxy auto-poll challenge in waiting_auth

- **GIVEN** run 进入 `waiting_auth`
- **AND** engine/provider 的会话 transport 声明了 `session_behavior.input_required=false`
- **WHEN** 后端创建 `PendingAuth`
- **THEN** payload MUST 继续提供 `auth_url` 与 `user_code`
- **AND** `accepts_chat_input` MUST 为 `false`
- **AND** `input_kind` MUST 为 `null`
- **AND** run MUST 保持 `waiting_auth`，直到 canonical `auth.completed`

### Requirement: Chat input MUST support auth submission without leaking secrets

系统 MUST 允许在同一聊天输入框中提交 `auth_code_or_url` 或 API Key，并保证 raw secret 不进入历史、审计和事件 payload。

#### Scenario: auth_code_or_url submission

- **WHEN** 用户在 `waiting_auth` 状态下提交 redirect URL 或 authorization code
- **THEN** 系统必须接受该输入并发出 `auth.input.accepted`
- **AND** 不得将 raw code / URL 写入消息历史或审计日志

### Requirement: Successful auth MUST resume in the same run with a new attempt

auth 完成后，系统 MUST 在同一 `run_id`、同一工作目录 / 执行环境下，以新的 `attempt` 恢复执行。

#### Scenario: 聊天输入完成恢复

- **WHEN** 用户提交的 `auth_code_or_url` 或 API Key 使 auth session 成功完成
- **THEN** 系统必须发出 `auth.completed`
- **AND** 以新的 `attempt` 重新执行该 run
