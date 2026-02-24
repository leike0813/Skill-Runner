## MODIFIED Requirements

### Requirement: 状态机事件 MUST 映射到 FCMP 显式状态事件
系统 MUST 将 canonical 状态机事件映射为 FCMP `conversation.state.changed`。

#### Scenario: running -> waiting_user
- **WHEN** 触发 `turn.needs_input`
- **THEN** FCMP 输出 `conversation.state.changed(from=running,to=waiting_user,trigger=turn.needs_input)`

#### Scenario: waiting_user -> queued（用户回复）
- **WHEN** 触发 `interaction.reply.accepted`
- **THEN** FCMP 输出 `interaction.reply.accepted`
- **AND** 输出 `conversation.state.changed(from=waiting_user,to=queued,trigger=interaction.reply.accepted)`

#### Scenario: waiting_user -> queued（自动决策）
- **WHEN** 触发 `interaction.auto_decide.timeout`
- **THEN** FCMP 输出 `interaction.auto_decide.timeout`
- **AND** 输出 `conversation.state.changed(from=waiting_user,to=queued,trigger=interaction.auto_decide.timeout)`
