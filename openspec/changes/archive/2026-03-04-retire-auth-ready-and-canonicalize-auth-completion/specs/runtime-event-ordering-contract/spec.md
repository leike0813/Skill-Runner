## ADDED Requirements

### Requirement: Auth completion ordering MUST depend on canonical completion source only
系统 MUST 仅允许 canonical auth completion source 解锁 `auth.completed` 与 `waiting_auth -> queued`。

#### Scenario: challenge and busy cannot unlock completion
- **WHEN** 系统发布 `auth.challenge.updated`、`auth.session.busy` 或相关 diagnostic event
- **THEN** 这些事件 MUST NOT 解锁 `auth.completed`
- **AND** MUST NOT 解锁 `conversation.state.changed(waiting_auth -> queued)`

### Requirement: Legacy auth_ready semantics MUST be removed from ordering rules
顺序合同 MUST 明确 `auth_ready` 已退役，readiness-like signal 不得参与 completion ordering。

#### Scenario: readiness-like signal is non-authoritative
- **WHEN** 系统观察到凭据可用、CLI 可执行或类似 readiness-like signal
- **THEN** 该信号 MAY 进入 observability
- **AND** MUST NOT 作为 auth completion 排序前置或释放条件
