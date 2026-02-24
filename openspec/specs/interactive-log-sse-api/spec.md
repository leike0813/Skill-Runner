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

### Requirement: `chat_event` 输出 MUST 满足 FCMP Schema
系统 MUST 在 SSE 输出前执行 FCMP schema 校验。

#### Scenario: chat_event 合法输出
- **WHEN** 服务端输出 `event=chat_event`
- **THEN** 事件满足 `fcmp_event_envelope` 合同

### Requirement: history 读取 MUST 兼容旧脏数据
系统 MUST 对历史中的不合规事件进行过滤，不得中断整体读取。

#### Scenario: 旧事件不合规
- **WHEN** history 中存在不满足 schema 的旧行
- **THEN** 服务端忽略该行并继续返回其余合法事件

### Requirement: 关键 FCMP 事件 MUST 满足配对不变量
系统 MUST 保证 waiting/reply/auto-decide 对应的 FCMP 事件配对关系成立。

#### Scenario: waiting_user 配对约束
- **WHEN** 输出 `conversation.state.changed(to=waiting_user)`
- **THEN** 同一事件序列中存在 `user.input.required`

#### Scenario: reply/timeout 配对约束
- **WHEN** 输出 `interaction.reply.accepted` 或 `interaction.auto_decide.timeout`
- **THEN** 后续存在 `conversation.state.changed(waiting_user->queued)` 且 trigger 与该事件类型一致

### Requirement: FCMP seq MUST 单调连续
系统 MUST 保证单次 materialize 的 FCMP 事件 `seq` 从 1 开始严格递增且无空洞。

#### Scenario: seq 连续
- **WHEN** 客户端获取一组 FCMP 历史或流式事件
- **THEN** `seq` 形成连续整数序列
