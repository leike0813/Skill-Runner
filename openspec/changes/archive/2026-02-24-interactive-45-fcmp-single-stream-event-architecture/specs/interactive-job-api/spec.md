## MODIFIED Requirements

### Requirement: Job 事件流 API MUST 使用 FCMP cursor
系统 MUST 使用 FCMP `seq` 作为 `cursor` 语义，不再使用 RASP `run_event.seq`。

#### Scenario: cursor 续传
- **WHEN** 客户端传入 `cursor=n`
- **THEN** 服务端从 `chat_event.seq > n` 继续推送

### Requirement: events/history MUST 返回 FCMP 历史
系统 MUST 返回 FCMP 历史事件序列，供断线补偿与回放消费。

#### Scenario: 历史拉取
- **WHEN** 客户端调用 `/events/history?from_seq=...&to_seq=...`
- **THEN** 返回有序 FCMP 事件列表
- **AND** 事件 `protocol_version` 为 `fcmp/1.0`
