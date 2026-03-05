# in-conversation-auth-method-selection Specification

## Purpose
TBD - created by archiving change refine-in-conversation-auth-method-selection-and-session-timeout. Update Purpose after archive.
## Requirements
### Requirement: 多方式鉴权 MUST 先选方式再创建 auth session
系统 MUST 在多方式场景先完成方式选择，再创建 auth session。

#### Scenario: 多方式 provider 进入方式选择
- **GIVEN** 会话型 run 命中高置信度 `auth_detection`
- **AND** engine/provider 支持多种鉴权方式
- **WHEN** run 进入 `waiting_auth`
- **THEN** 系统 MUST 返回 `available_methods`
- **AND** MUST NOT 在用户选择前创建 auth session

#### Scenario: 单一方式 provider 直接进入 challenge
- **GIVEN** engine/provider 仅支持单一鉴权方式
- **WHEN** run 进入 `waiting_auth`
- **THEN** 系统 MAY 直接创建 auth session
- **AND** phase MUST 为 `challenge_active`

### Requirement: callback 鉴权 MUST 同时支持自动 callback 与手工 callback URL
系统 MUST 同时支持自动 callback 完成与手工粘贴 callback URL 完成。

#### Scenario: callback challenge 提供两种完成路径
- **GIVEN** 用户选择 `callback`
- **WHEN** auth challenge 已创建
- **THEN** challenge MUST 提供 auth link
- **AND** 系统 MUST 接受手工粘贴的 callback URL

### Requirement: 鉴权输入种类 MUST 区分 callback_url / authorization_code / api_key
系统 MUST 将鉴权提交种类规范化为 `callback_url`、`authorization_code` 或 `api_key`。

#### Scenario: callback URL 提交
- **WHEN** 用户在聊天窗口中提交 callback URL
- **THEN** submission kind MUST 为 `callback_url`

#### Scenario: 授权码提交
- **WHEN** 用户在聊天窗口中提交授权码
- **THEN** submission kind MUST 为 `authorization_code`

#### Scenario: API Key 提交
- **WHEN** 用户在聊天窗口中提交 API Key
- **THEN** submission kind MUST 为 `api_key`

### Requirement: auth session timeout MUST be session-scoped
auth timeout MUST 仅在 auth session 进入 challenge 活跃阶段后生效。

#### Scenario: method_selection 不计时
- **GIVEN** run 处于 `waiting_auth`
- **AND** phase 为 `method_selection`
- **THEN** 系统 MUST NOT 启动 auth timeout

#### Scenario: challenge_active 开始计时
- **GIVEN** auth session 创建成功
- **WHEN** phase 变为 `challenge_active`
- **THEN** 系统 MUST 开始 auth session timeout

### Requirement: 后端 MUST 提供 auth session timeout/status 真相
后端 MUST 对外提供可用于倒计时与状态判断的 auth session 时间字段与状态字段。

#### Scenario: 前端同步 auth session 状态
- **WHEN** 客户端调用 auth session 状态接口
- **THEN** 后端 MUST 返回 `timeout_sec`、`created_at`、`expires_at`、`server_now`、`timed_out`

### Requirement: busy 与提交失败 MUST 显式可见
系统 MUST 对 busy 阻塞与提交失败返回显式可见错误，而不是静默吞掉。

#### Scenario: 活跃 auth session 阻塞
- **WHEN** 新 auth session 因已有活跃 session 无法创建
- **THEN** run MUST 保持 `waiting_auth`
- **AND** 客户端 MUST 收到显式错误

#### Scenario: 提交失败
- **WHEN** auth submission 返回非成功结果
- **THEN** 客户端 MUST 显示错误
- **AND** MUST NOT 静默吞掉失败

### Requirement: waiting_auth 的 method selection MUST 来源于策略文件

系统 MUST 使用统一策略服务计算会话内 `available_methods`，禁止在编排器中硬编码 engine/provider 对应方法列表。

#### Scenario: waiting_auth method selection uses strategy-defined conversation methods
- **GIVEN** run 进入 `waiting_auth`
- **WHEN** 系统构造 `PendingAuthMethodSelection`
- **THEN** `available_methods` MUST 来自策略文件中该 engine/provider 的 in-conversation methods
- **AND** `ask_user.options` MUST 与 `available_methods` 一致

### Requirement: 会话内鉴权 MUST 固定使用策略声明的 in-conversation transport

会话内鉴权流程 MUST 按策略声明的 `in_conversation.transport` 计算可用方法；本阶段不向用户暴露 transport 选择。

#### Scenario: in-conversation transport is oauth_proxy
- **WHEN** 系统在会话内计算可用鉴权方式
- **THEN** 仅使用策略声明的会话 transport（当前为 `oauth_proxy`）
- **AND** 客户端交互仍只选择 auth_method

