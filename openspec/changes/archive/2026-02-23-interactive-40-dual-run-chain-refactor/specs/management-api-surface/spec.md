## MODIFIED Requirements

### Requirement: Management run read path MUST enforce parity for interaction/history/range
管理层 run 读取能力 MUST 以 source capability matrix 为约束，并确保 `pending/reply/history/range` 在 installed 与 temp 上对外行为一致。

#### Scenario: Source-aware read behavior
- **WHEN** 管理层读取 run 状态/日志/事件/结果
- **THEN** 共用能力通过统一 read facade 提供
- **AND** `pending/reply/history/range` 在 installed 与 temp 上都可用且语义一致
