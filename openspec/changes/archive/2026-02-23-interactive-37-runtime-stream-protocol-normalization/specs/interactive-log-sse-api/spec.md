## MODIFIED Requirements

### Requirement: 系统 MUST 提供运行日志 SSE 事件流接口
系统 MUST 为 jobs 与 temp-skill-runs 提供标准 SSE 事件流，并以统一运行时事件协议输出结构化事件。

#### Scenario: 建立 Jobs 事件流
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 事件流包含统一结构化运行事件（如 `event=run_event`，payload 为 RASP）

#### Scenario: 建立 Temp Skill 事件流
- **WHEN** 客户端调用 `GET /v1/temp-skill-runs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 事件语义与 jobs 事件流一致

### Requirement: 系统 MUST 支持断线后按 cursor 恢复
系统 MUST 支持基于事件序号的断线恢复。

#### Scenario: 基于 cursor 的重连
- **WHEN** 客户端携带 `cursor` 重新连接
- **THEN** 服务端从 `cursor` 之后的下一条事件继续推送
- **AND** 不重复发送已确认事件

## ADDED Requirements

### Requirement: 事件流 MUST 暴露解析与转译诊断
系统 MUST 在事件流中提供解析与转译诊断事件，确保前端与排障系统可见不确定性与降级路径。

#### Scenario: 解析降级时发送诊断事件
- **WHEN** 运行中输出无法被 profile 稳定解析
- **THEN** 服务端发送 `diagnostic` 类事件
- **AND** 诊断中包含错误码或告警码（如 `PTY_FALLBACK_USED`、`LOW_CONFIDENCE_PARSE`）

### Requirement: 系统 MUST 提供运行事件历史回放接口
系统 MUST 提供结构化运行事件的历史拉取能力，支持按 `seq` 与时间区间检索，便于排障与复盘。

#### Scenario: 按 seq 区间回放
- **WHEN** 客户端请求历史事件并提供 `from_seq/to_seq`
- **THEN** 服务端返回该区间内的有序 `run_event` 列表
- **AND** 返回结果可用于与 SSE 流衔接，避免事件缺口

#### Scenario: 按时间区间回放
- **WHEN** 客户端请求历史事件并提供 `from_ts/to_ts`
- **THEN** 服务端返回该时间范围内的有序 `run_event` 列表
- **AND** 每条事件保留 `seq` 与 `ts`，用于前端建立时间线与关联关系
