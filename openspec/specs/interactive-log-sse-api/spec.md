# interactive-log-sse-api Specification

## Purpose
TBD - created by archiving change interactive-25-api-sse-log-streaming. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供运行日志 SSE 事件流接口
系统 MUST 为 jobs 与 temp-skill-runs 提供标准 SSE 事件流，以实时暴露运行中的 stdout/stderr 与状态变化。

#### Scenario: 建立 Jobs 事件流
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 首帧包含 `snapshot` 事件

#### Scenario: 建立 Temp Skill 事件流
- **WHEN** 客户端调用 `GET /v1/temp-skill-runs/{request_id}/events`
- **THEN** 服务端返回 `text/event-stream`
- **AND** 事件语义与 jobs 事件流一致

### Requirement: 系统 MUST 以增量方式发送 stdout/stderr
系统 MUST 发送带 offset 的 stdout/stderr 增量事件，避免客户端反复下载全量日志。

#### Scenario: stdout 增量事件
- **WHEN** 运行期间 stdout 文件追加新内容
- **THEN** 服务端发送 `event=stdout`
- **AND** 载荷包含 `from`, `to`, `chunk`

#### Scenario: stderr 增量事件
- **WHEN** 运行期间 stderr 文件追加新内容
- **THEN** 服务端发送 `event=stderr`
- **AND** 载荷包含 `from`, `to`, `chunk`

### Requirement: 系统 MUST 支持断线后按 offset 恢复
系统 MUST 允许客户端通过请求参数携带起始 offset，从指定位置继续消费事件流。

#### Scenario: 指定 offset 重连
- **WHEN** 客户端以 `stdout_from` / `stderr_from` 重新连接
- **THEN** 服务端从该 offset 后的位置继续发送增量
- **AND** 不重复发送已确认区间

### Requirement: 事件流 MUST 提供保活与帧大小控制
系统 MUST 提供 heartbeat 保活事件，并限制单帧 `chunk` 的最大大小，避免长连接静默或超大帧压垮客户端。

#### Scenario: heartbeat 保活
- **WHEN** 一段时间内无 stdout/stderr/status 增量
- **THEN** 服务端发送 `event=heartbeat`
- **AND** 客户端可据此判断连接存活

#### Scenario: chunk 分片发送
- **WHEN** 单次日志增量超过服务端帧大小阈值
- **THEN** 服务端将增量拆分为多帧发送
- **AND** 每帧 `chunk` 不超过上限
- **AND** `from/to` 仍保持连续可重建

### Requirement: waiting_user 与终态 MUST 有明确结束语义
系统 MUST 在 run 被取消时向 SSE 客户端发出可识别终态事件。

#### Scenario: 取消后事件流终止
- **GIVEN** 客户端已订阅 run 的 SSE 事件流
- **WHEN** run 因用户取消进入 `canceled`
- **THEN** 事件流发送 `status=canceled` 的终态事件
- **AND** 事件中可包含取消原因（如 `CANCELED_BY_USER`）
- **AND** 客户端可据此安全停止后续轮询或重连

