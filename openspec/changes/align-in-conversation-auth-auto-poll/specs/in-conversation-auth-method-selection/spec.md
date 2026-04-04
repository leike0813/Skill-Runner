## MODIFIED Requirements

### Requirement: 鉴权输入种类 MUST 区分 callback_url / auth_code_or_url / api_key

系统 MUST 将鉴权提交种类规范化为 `callback_url`、`auth_code_or_url` 或 `api_key`。

#### Scenario: auth code or redirect URL submission

- **WHEN** 用户在聊天窗口中提交 redirect URL 或授权码
- **THEN** submission kind MUST 为 `auth_code_or_url`

### Requirement: 会话内鉴权 MUST 固定使用策略声明的 in-conversation transport

会话内鉴权流程 MUST 按策略声明的 `in_conversation.transport` 计算 challenge 语义；本阶段不向用户暴露 transport 选择。

#### Scenario: waiting_auth consumes declared session behavior

- **WHEN** 系统在会话内基于策略 transport 构造 challenge
- **THEN** `accepts_chat_input` 与 `input_kind` MUST 与该 transport 的 `session_behavior` 一致
- **AND** 不得在编排器中为特定 engine 手写隐藏输入框分支
