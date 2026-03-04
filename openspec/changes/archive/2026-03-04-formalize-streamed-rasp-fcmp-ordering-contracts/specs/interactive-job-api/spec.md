## ADDED Requirements

### Requirement: Live SSE MUST expose only canonical conversation lifecycle FCMP
系统 MUST 仅通过 canonical lifecycle FCMP 对外表达 conversation 生命周期，不得继续暴露冗余的 terminal lifecycle 事件。

#### Scenario: terminal lifecycle is represented by state.changed only
- **WHEN** run 进入 `succeeded`、`failed` 或 `canceled`
- **THEN** `/events` MUST 通过 terminal `conversation.state.changed` 表达该生命周期变化
- **AND** MUST NOT 额外发送 `conversation.completed` 或 `conversation.failed`

### Requirement: Live SSE MUST preserve canonical FCMP publish order
系统 MUST 以 canonical FCMP publish order 向 `/events` 推送 active run 的会话事件，且该顺序 MUST NOT 被 audit mirror、history materialization 或 batch backfill 重新定义。

#### Scenario: active SSE follows canonical publish order
- **WHEN** active run 依次发布多条 parser-originated 与 orchestration-originated FCMP
- **THEN** `/events` MUST 按它们的 canonical publish order 推送
- **AND** MUST NOT 因 audit mirror 写盘时序改变相对顺序

### Requirement: events/history MUST preserve the same causal order as live delivery
系统 MUST 保证 `/events/history` 返回的事件顺序与该 run 的 canonical FCMP publish order 一致，即使读取路径采用 memory-first 或 audit fallback。

#### Scenario: history replay matches live order
- **WHEN** 客户端对同一 run 请求某个 cursor 范围内的 `/events/history`
- **THEN** 返回事件顺序 MUST 与该范围内 live delivery 的 canonical order 一致
- **AND** audit fallback MUST NOT 重排已发布事件

### Requirement: Auth guidance MUST precede dependent auth challenge publication
系统 MUST 保证任何依赖用户选择鉴权方式的 challenge/link 发布都晚于对应的 auth 引导事件。

#### Scenario: auth selection guidance precedes challenge link
- **WHEN** run 需要用户先选择鉴权方式再处理 challenge
- **THEN** 面向用户的方式选择引导 MUST 先于 challenge/link 事件可见
- **AND** 用户 MUST NOT 先看到 challenge/link 再看到选择说明

#### Scenario: single-method auth does not surface method selection
- **WHEN** 某条 auth route 只有单一可用方式
- **THEN** API 与 SSE MUST 直接暴露 challenge-active payload
- **AND** MUST NOT 暴露 method-selection UI

### Requirement: Terminal summaries and results MUST NOT outrun canonical terminal lifecycle events
系统 MUST 禁止 terminal summary、terminal result 或等价终态投影在 canonical terminal `conversation.state.changed` 前置条件满足之前对外可见。

#### Scenario: waiting state does not expose terminal result
- **GIVEN** run 仍处于 `waiting_user` 或 `waiting_auth`
- **WHEN** 客户端读取会话事件、summary 或结果投影
- **THEN** 系统 MUST NOT 暴露空的 terminal result 或 terminal summary

#### Scenario: terminal projection waits for terminal state change
- **WHEN** run 进入 terminal
- **THEN** final summary/result 只有在对应 terminal `conversation.state.changed` 前置条件满足后才可见
