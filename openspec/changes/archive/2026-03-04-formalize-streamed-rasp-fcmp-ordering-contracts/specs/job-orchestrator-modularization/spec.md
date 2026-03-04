## ADDED Requirements

### Requirement: Orchestration-originated lifecycle FCMP MUST flow through the shared ordering publisher
系统 MUST 要求所有 orchestration-originated lifecycle FCMP 通过共享 publisher 进入 canonical FCMP 时间线，禁止 orchestration、observability 或 history 路径绕过 publisher 自行拼装或重排 lifecycle FCMP。

#### Scenario: lifecycle state transition enters the shared FCMP timeline
- **WHEN** orchestration 发布 `conversation.state.changed`、`interaction.reply.accepted`、`auth.completed` 或其他 lifecycle 相关 FCMP
- **THEN** 这些事件 MUST 通过共享 ordering publisher 发布
- **AND** MUST 与 parser-originated FCMP 处于同一 canonical FCMP timeline

### Requirement: Orchestration MUST NOT emit redundant terminal lifecycle FCMP
系统 MUST 不再由 orchestration 额外发布 `conversation.completed` 或 `conversation.failed`，terminal lifecycle 语义 MUST 折叠进 `conversation.state.changed.data.terminal`。

#### Scenario: terminal state uses state.changed only
- **WHEN** orchestration 处理 run terminal
- **THEN** 仅发布 terminal `conversation.state.changed`
- **AND** 不再追加冗余 terminal lifecycle 事件

### Requirement: Result projection MUST respect canonical event gating
系统 MUST 将 final summary、result projection 和其他 terminal-facing 输出视为投影，而不是源事件，并且这些投影 MUST 受 canonical event gating 约束。

#### Scenario: projection cannot outrun waiting state truth
- **GIVEN** orchestration 仍将 run 视为 `waiting_user` 或 `waiting_auth`
- **WHEN** terminal-facing projection 被计算或读取
- **THEN** 系统 MUST NOT 先暴露 terminal projection

#### Scenario: projection cannot outrun terminal causal prerequisites
- **WHEN** orchestration 计算 terminal summary 或 result projection
- **THEN** 它 MUST 先确认对应 canonical terminal lifecycle 前置条件已经满足
- **AND** MUST NOT 因 audit/backfill 已可用而跳过该 gating

### Requirement: Waiting, reply, and resume lifecycle publication MUST preserve causal order
系统 MUST 保证 waiting、reply accepted 与 resumed running 的发布顺序符合因果链，且不得出现 resumed running 早于 reply accepted 已发布的情况。

#### Scenario: resumed running follows reply accepted
- **WHEN** 用户提交合法 reply 并触发 resumed attempt
- **THEN** `interaction.reply.accepted` MUST 先进入 canonical FCMP timeline
- **AND** 对应 resumed attempt 的 `running` MUST 晚于该事件发布
