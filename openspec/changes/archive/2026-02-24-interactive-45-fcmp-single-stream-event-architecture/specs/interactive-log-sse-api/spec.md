## MODIFIED Requirements

### Requirement: 系统 MUST 提供 FCMP 单流 SSE 事件接口
系统 MUST 通过 `chat_event` 提供统一业务事件流，不再要求客户端消费 RASP 或日志增量侧带事件。

#### Scenario: 建立 Jobs 事件流
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 首帧包含 `snapshot`
- **AND** 业务事件通过 `event=chat_event` 输出

### Requirement: SSE 业务事件 MUST 移除 legacy 双轨依赖
系统 MUST 不再以 `run_event/status/stdout/stderr/end` 作为对外业务语义契约。

#### Scenario: 事件面收敛
- **WHEN** 客户端持续消费事件流
- **THEN** 业务语义由 `chat_event` 承载
- **AND** `heartbeat` 仅作为连接保活事件

### Requirement: waiting_user 与终态语义 MUST 由 FCMP 事件表达
系统 MUST 通过 FCMP 明确表达状态流转与终态，而非通过 `status/end` 侧带事件表达。

#### Scenario: waiting_user 状态
- **WHEN** run 进入 `waiting_user`
- **THEN** FCMP 输出 `conversation.state.changed(to=waiting_user)`
- **AND** 输出 `user.input.required`

#### Scenario: canceled 终态
- **WHEN** run 被取消进入 `canceled`
- **THEN** FCMP 输出 `conversation.state.changed(to=canceled)`
- **AND** 输出 `conversation.failed(error.code=CANCELED)`
