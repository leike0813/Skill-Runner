## ADDED Requirements

### Requirement: Waiting-auth resume MUST require canonical auth completion
系统 MUST 仅在 canonical `auth.completed` 之后推进 `waiting_auth -> queued` 与后续 resumed attempt。

#### Scenario: challenge-active polling does not resume
- **WHEN** run 处于 `waiting_auth`
- **AND** 当前 auth session 仍为 non-terminal challenge-active snapshot
- **THEN** repeated detail/list polling MUST NOT issue resume ticket
- **AND** run MUST remain `waiting_auth`

### Requirement: Single-method busy recovery MUST preserve actionable challenge
系统 MUST 在单方式鉴权 busy recovery 时恢复或重投影现有 challenge，而不是推进 resume 或要求重新选择方式。

#### Scenario: single-method busy recovery stays in waiting_auth
- **WHEN** 单方式 auth route 命中已有 active auth session
- **THEN** 用户继续看到当前 challenge
- **AND** 系统 MUST NOT 进入 `queued` 或 `running`
