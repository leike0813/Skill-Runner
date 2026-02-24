## ADDED Requirements

### Requirement: FCMP cursor MUST be monotonic and reconnect-safe
系统 MUST 保证 `chat_event.seq` 单调递增，支持断线后按 cursor 续传。

#### Scenario: cursor 续传
- **GIVEN** 客户端已消费至 `chat_event.seq = N`
- **WHEN** 客户端重连并传入 `cursor=N`
- **THEN** 服务端仅推送 `seq > N` 的事件

### Requirement: FCMP history MUST support seq/time filters
系统 MUST 支持按 `from_seq/to_seq/from_ts/to_ts` 拉取 FCMP 历史。

#### Scenario: seq 区间拉取
- **WHEN** 客户端传入 `from_seq` 与 `to_seq`
- **THEN** 返回区间内有序 FCMP 事件

#### Scenario: 时间区间拉取
- **WHEN** 客户端传入 `from_ts` 与 `to_ts`
- **THEN** 返回时间范围内有序 FCMP 事件
