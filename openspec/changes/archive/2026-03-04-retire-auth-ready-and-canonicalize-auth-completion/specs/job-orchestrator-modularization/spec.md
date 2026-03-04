## ADDED Requirements

### Requirement: Orchestration MUST gate auth resume on canonical completion only
orchestration MUST 仅根据 canonical auth session terminal success 生成 `auth.completed`、resume ticket 和 `waiting_auth -> queued` 转移。

#### Scenario: readiness-like signal cannot trigger resume
- **WHEN** engine 静态凭据状态已变为可用
- **AND** auth session snapshot 仍为 `waiting_user` 或 `challenge_active`
- **THEN** orchestration MUST NOT issue resume ticket
- **AND** MUST NOT start a new attempt

### Requirement: Waiting-auth reconciliation MUST be idempotent for non-terminal snapshots
系统 MUST 保证 waiting-auth reconcile 在 non-terminal challenge snapshot 上是幂等的。

#### Scenario: repeated reconcile does not advance active challenge
- **WHEN** observability 多次触发 waiting-auth reconcile
- **AND** snapshot 尚未 terminal success
- **THEN** run 状态保持 `waiting_auth`
- **AND** pending auth 保持 challenge-active
