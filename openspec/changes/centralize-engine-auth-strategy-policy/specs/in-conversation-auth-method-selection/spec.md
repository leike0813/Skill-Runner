## ADDED Requirements

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
