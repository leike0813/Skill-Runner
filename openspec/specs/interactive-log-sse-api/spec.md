# interactive-log-sse-api Specification

## Purpose
定义 run 观测 SSE 的 FCMP 单流契约。

## Requirements

### Requirement: 系统 MUST 提供 FCMP 单流 SSE 接口
系统 MUST 为 jobs 与 temp-skill-runs 提供统一 `chat_event` 业务流。

#### Scenario: 建立 Jobs 事件流
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 首帧包含 `snapshot`
- **AND** 后续业务事件通过 `event=chat_event` 发送

#### Scenario: 建立 Temp Skill 事件流
- **WHEN** 客户端调用 `GET /v1/temp-skill-runs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 事件语义与 jobs 事件流一致

### Requirement: SSE MUST 提供保活且不暴露 legacy 业务事件
系统 MUST 提供 heartbeat 保活；`run_event/status/stdout/stderr/end` 不再作为对外业务契约。

#### Scenario: heartbeat 保活
- **WHEN** 一段时间内无新的 chat_event
- **THEN** 服务端发送 `event=heartbeat`

### Requirement: waiting_user 与终态语义 MUST 由 FCMP 表达
系统 MUST 通过 FCMP 状态事件表达 waiting/terminal，而非 status/end 侧带事件。

#### Scenario: waiting_user
- **WHEN** run 进入 `waiting_user`
- **THEN** FCMP 输出 `conversation.state.changed(to=waiting_user)`
- **AND** 输出 `user.input.required`

#### Scenario: canceled
- **WHEN** run 进入 `canceled`
- **THEN** FCMP 输出 `conversation.state.changed(to=canceled)`
- **AND** 输出 `conversation.failed(error.code=CANCELED)`
