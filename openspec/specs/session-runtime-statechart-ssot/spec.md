# session-runtime-statechart-ssot Specification

## Purpose
定义 session 运行时状态机 SSOT，约束实现、协议和测试一致演进。
## Requirements
### Requirement: 系统 MUST 维护统一 canonical 状态机
系统 MUST 以 `queued/running/waiting_user/waiting_auth/succeeded/failed/canceled` 作为唯一 canonical 状态集合。

#### Scenario: auth 进入可恢复等待态
- **GIVEN** run 处于 `running`
- **WHEN** 触发 `auth.required`
- **THEN** run 必须转为 `waiting_auth`

#### Scenario: auth 成功后重新排队
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 触发 `auth.completed`
- **THEN** run 必须转为 `queued`
- **AND** 后续由编排器以新 `attempt` 恢复执行

#### Scenario: auth 失败收敛为终态
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 触发 `auth.failed`
- **THEN** run 必须转为 `failed`

### Requirement: 系统 MUST 以状态机事件驱动关键分支
系统 MUST 使用显式事件集合驱动状态转换，而不是散落条件分支；`waiting_auth` 必须使用专门 auth 事件族，而不是复用 `waiting_user` 事件。

#### Scenario: auth 输入被接受
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 接收 `auth.input.accepted`
- **THEN** run 维持 `waiting_auth`

#### Scenario: challenge 更新
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 接收 `auth.challenge.updated`
- **THEN** run 维持 `waiting_auth`

### Requirement: 重启恢复 MUST 使用统一恢复事件
系统 MUST 通过统一恢复事件收敛 `waiting_user` 的启动恢复分流。

#### Scenario: 恢复保留 waiting
- **GIVEN** run 处于 `waiting_user`
- **AND** pending + session handle 有效
- **WHEN** orchestrator 启动恢复
- **THEN** 触发 `restart.preserve_waiting`
- **AND** run 维持 `waiting_user`

#### Scenario: 恢复失败收敛
- **GIVEN** run 处于 `waiting_user`
- **AND** pending 或 session handle 无效
- **WHEN** orchestrator 启动恢复
- **THEN** 触发 `restart.reconcile_failed`
- **AND** run 转为 `failed`

### Requirement: auto MUST 作为 interactive 子集建模
系统 MUST 将 `auto` 建模为同一状态机下的策略子集，而非独立核心状态机。

#### Scenario: auto 终态映射一致
- **WHEN** run 处于 `auto` 模式
- **THEN** 终态仍仅为 `succeeded|failed|canceled`
- **AND** 协议终态映射与 interactive 一致

### Requirement: canonical 状态事件 MUST 映射到 FCMP 显式事件
系统 MUST 为 `waiting_auth` 的关键转换输出专门的 FCMP auth 事件和 `conversation.state.changed`。

#### Scenario: auth required ordering
- **WHEN** run 进入 `waiting_auth`
- **THEN** FCMP 必须先输出 `auth.required`
- **AND** 再输出 `conversation.state.changed(from=running,to=waiting_auth,trigger=auth.required)`

#### Scenario: auth completed ordering
- **WHEN** auth session 成功完成
- **THEN** FCMP 必须先输出 `auth.completed`
- **AND** 再输出 `conversation.state.changed(from=waiting_auth,to=queued,trigger=auth.completed)`

### Requirement: 状态与回复事件 payload MUST 满足固定字段合同
系统 MUST 对关键状态与交互事件 payload 执行 schema 校验。

#### Scenario: state.changed 字段完整
- **WHEN** 输出 `conversation.state.changed`
- **THEN** payload 包含 `from`、`to`、`trigger`、`updated_at`

#### Scenario: reply.accepted 字段完整
- **WHEN** 输出 `interaction.reply.accepted`
- **THEN** payload 包含 `interaction_id`、`resolution_mode=user_reply`、`accepted_at`

#### Scenario: auto_decide.timeout 字段完整
- **WHEN** 输出 `interaction.auto_decide.timeout`
- **THEN** payload 包含 `interaction_id`、`resolution_mode=auto_decide_timeout`、`policy`

### Requirement: canonical 状态机不变量 MUST 合同化并由模型测试守护
系统 MUST 将 canonical 状态/转移不变量沉淀为机器可读合同，并由模型测试校验实现一致性。

#### Scenario: 合同-实现转移一致
- **WHEN** 执行状态机模型测试
- **THEN** 合同转移集合与实现转移集合双向等价

#### Scenario: 有限序列等价
- **WHEN** 对有限事件序列进行模型回放
- **THEN** 合同模型与实现模型得到相同的状态结果

### Requirement: waiting-state applicability MUST follow execution-mode and conversation-mode matrix
The canonical runtime statechart MUST treat `execution_mode` and `client_metadata.conversation_mode` as orthogonal inputs.

#### Scenario: session-capable auto run hits auth
- **GIVEN** a run uses `execution_mode=auto`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** high-confidence auth is detected
- **THEN** the canonical statechart MUST allow `running -> waiting_auth`

#### Scenario: session-capable interactive run needs user reply
- **GIVEN** a run uses `execution_mode=interactive`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** the turn requires user reply
- **THEN** the canonical statechart MUST allow `running -> waiting_user`

#### Scenario: non-session client cannot sustain waiting states
- **GIVEN** a run uses `client_metadata.conversation_mode=non_session`
- **WHEN** the turn would otherwise require auth or user reply
- **THEN** the backend MUST NOT expose real `waiting_auth` or `waiting_user`
- **AND** non-session interactive execution MUST be normalized to zero-timeout auto-reply when needed

### Requirement: process events MUST NOT mutate canonical session states
Process events SHALL NOT mutate canonical state transitions.

#### Scenario: publishing reasoning/tool/command events
- **GIVEN** run 正处于任一非终态
- **WHEN** 系统发布 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`
- **THEN** canonical conversation state MUST remain unchanged

### Requirement: fallback promotion guard by target state
Fallback promotion MUST be state-gated by target status.

#### Scenario: fallback promotion state gate
- **GIVEN** 系统需要对可提升消息执行 fallback
- **WHEN** target status is `succeeded` or `waiting_user`
- **THEN** fallback promotion MAY execute
- **AND** when target status is `failed` or `canceled`, fallback promotion MUST NOT execute

