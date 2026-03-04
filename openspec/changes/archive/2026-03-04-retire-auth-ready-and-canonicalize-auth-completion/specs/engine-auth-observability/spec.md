## ADDED Requirements

### Requirement: Engine auth observability MUST retire legacy auth_ready semantics
系统 MUST 从 engine auth observability 中移除 `auth_ready`，并改用非 completion 语义的字段表达静态凭据状态。

#### Scenario: static engine auth observability returns credential_state
- **WHEN** 客户端查询 engine auth observability
- **THEN** 响应使用 `credential_state`
- **AND** MUST NOT 暴露 `auth_ready`

### Requirement: Static credential observability MUST be decoupled from runtime auth completion
系统 MUST 保证 engine 静态凭据状态不会被当成 runtime auth session completion 使用。

#### Scenario: credential present does not complete waiting-auth
- **WHEN** engine static `credential_state=present`
- **AND** waiting-auth session 尚未 terminal success
- **THEN** runtime MUST NOT 推进 `auth.completed`
- **AND** MUST NOT 离开 `waiting_auth`
