## ADDED Requirements

### Requirement: protocol history behavior MUST remain wire-compatible under single-source publishing
收敛到 live publisher 单源后，`protocol/history` 的外部接口 MUST 保持兼容。

#### Scenario: client polls protocol history during and after run completion
- **GIVEN** 客户端在 running 与 terminal 阶段轮询 `protocol/history`
- **WHEN** 读取 `stream=fcmp|rasp`
- **THEN** 响应字段形状 MUST 与既有接口兼容
- **AND** terminal 阶段 `source` 仍表示 `audit` 口径。
