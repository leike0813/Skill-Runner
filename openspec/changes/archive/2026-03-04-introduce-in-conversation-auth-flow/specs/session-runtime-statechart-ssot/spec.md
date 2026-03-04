## MODIFIED Requirements

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
