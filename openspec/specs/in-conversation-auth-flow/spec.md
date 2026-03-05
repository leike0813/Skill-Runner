# in-conversation-auth-flow Specification

## Purpose
TBD - created by archiving change introduce-in-conversation-auth-flow. Update Purpose after archive.
## Requirements
### Requirement: High-confidence auth detection in session runs MUST enter waiting_auth
系统 MUST 将会话型 run 中的高置信度 `auth_detection` 升级为可恢复的 `waiting_auth` 流程，而不是直接失败。

#### Scenario: 会话型 run 进入 waiting_auth
- **GIVEN** run 属于会话型客户端场景
- **AND** `auth_detection.confidence=high`
- **AND** 系统能够构造对应 engine/provider 的 auth session
- **WHEN** 编排器归一化当前 attempt 结果
- **THEN** run 必须进入 `waiting_auth`
- **AND** 不得进入 `failed`
- **AND** 不得进入 `waiting_user`

#### Scenario: 非会话 run 维持 AUTH_REQUIRED 失败
- **GIVEN** run 不属于会话型客户端场景
- **AND** `auth_detection.confidence=high`
- **WHEN** 编排器归一化当前 attempt 结果
- **THEN** run 必须继续按 `AUTH_REQUIRED` 失败处理

### Requirement: Auth challenge MUST be surfaced inside the chat session
系统 MUST 在聊天窗口内向用户呈现 auth prompt、链接和输入要求。

#### Scenario: 初次进入 waiting_auth
- **WHEN** run 首次进入 `waiting_auth`
- **THEN** 系统必须发出 `auth.required`
- **AND** payload 必须包含当前 challenge 所需的 prompt / instructions / auth URL / provider / input kind

#### Scenario: challenge 更新
- **WHEN** 用户提交了无效 auth 输入但流程仍可继续
- **THEN** 系统必须发出 `auth.challenge.updated`
- **AND** run 继续保持 `waiting_auth`

### Requirement: Chat input MUST support auth submission without leaking secrets
系统 MUST 允许在同一聊天输入框中提交 authorization code 或 API Key，并保证 raw secret 不进入历史、审计和事件 payload。

#### Scenario: 授权码提交
- **WHEN** 用户在 `waiting_auth` 状态下提交 authorization code
- **THEN** 系统必须接受该输入并发出 `auth.input.accepted`
- **AND** 不得将 raw code 写入消息历史或审计日志

#### Scenario: API Key 提交
- **WHEN** 用户在 `waiting_auth` 状态下提交 API Key
- **THEN** 系统必须接受该输入并发出 `auth.input.accepted`
- **AND** 不得将 raw key 写入消息历史或审计日志

### Requirement: Successful auth MUST resume in the same run with a new attempt
auth 完成后，系统 MUST 在同一 `run_id`、同一工作目录 / 执行环境下，以新的 `attempt` 恢复执行。

#### Scenario: OAuth callback 完成恢复
- **WHEN** 绑定到 run 的 auth session 通过 callback 成功完成
- **THEN** 系统必须发出 `auth.completed`
- **AND** run 状态从 `waiting_auth` 转为 `queued`
- **AND** 以新的 `attempt` 重新执行该 run

#### Scenario: 聊天输入完成恢复
- **WHEN** 用户提交的 authorization code 或 API Key 使 auth session 成功完成
- **THEN** 系统必须发出 `auth.completed`
- **AND** 以新的 `attempt` 重新执行该 run

### Requirement: Auth session failure MUST remain recoverable until deemed terminal
系统 MUST 区分可重试的 challenge 更新与不可恢复的 auth 失败。

#### Scenario: 可重试输入错误
- **WHEN** 用户提交了无效 auth 输入但仍可继续重试
- **THEN** 系统发出 `auth.challenge.updated`
- **AND** run 保持 `waiting_auth`

#### Scenario: 不可恢复 auth 失败
- **WHEN** flow manager 判定 auth session 不可继续
- **THEN** 系统必须发出 `auth.failed`
- **AND** run 从 `waiting_auth` 转为 `failed`

### Requirement: waiting_auth challenge 编排 MUST 受策略能力约束

系统 MUST 仅在策略文件声明支持的组合下进入 waiting_auth challenge 编排路径。

#### Scenario: unsupported combination does not create pending auth
- **GIVEN** auth detection 命中 `auth_required/high`
- **AND** 当前 engine/provider 在策略文件中无会话可用方式
- **WHEN** 编排器尝试创建 pending auth
- **THEN** 系统 MUST NOT 创建 pending auth challenge

#### Scenario: single supported method directly starts challenge
- **GIVEN** 当前 engine/provider 在策略文件中仅有一个会话可用方式
- **WHEN** run 进入 waiting_auth
- **THEN** 系统 MAY 直接创建 challenge_active
- **AND** challenge 的 `auth_method` MUST 与策略结果一致

