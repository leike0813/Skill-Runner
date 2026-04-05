## ADDED Requirements

### Requirement: auth submission kinds MUST be canonical

Auth submission kinds MUST include `callback_url`, `auth_code_or_url`, and `api_key`.

#### Scenario: auth reply payload uses auth_code_or_url

- **WHEN** 客户端在 `waiting_auth` 阶段提交人工 OAuth 返回内容
- **THEN** `submission.kind` MUST 为 `auth_code_or_url`

### Requirement: pending auth payload MUST expose inputless auto-poll challenges

交互式 run 在 `waiting_auth` 中 MUST 能表达“展示链接但不接收聊天输入”的 challenge。

#### Scenario: waiting_auth returns auth_url with no input box

- **GIVEN** 后端生成的 pending auth challenge 不要求聊天输入
- **WHEN** 客户端读取 pending/auth status
- **THEN** payload MUST 返回 `accepts_chat_input=false`
- **AND** `input_kind` MUST 为 `null`
- **AND** 仍 MAY 返回 `auth_url` 与 `user_code`
