## ADDED Requirements

### Requirement: RASP raw rows MUST be coalesced for high-volume stderr bursts
在高频错误输出场景中，RASP raw 行 MUST 进行分块归并以降低事件数量与聚合成本。

#### Scenario: repeated stderr stack traces
- **GIVEN** 同 attempt 的 stderr 连续输出大量行
- **WHEN** 生成 RASP 事件
- **THEN** 服务端 MUST 将连续行归并为有限数量 `raw.stderr` 事件块
- **AND** 事件顺序 MUST 保持稳定

### Requirement: timeline aggregation MUST reuse cache when audit files are unchanged
`timeline/history` MUST 在审计文件未变更时复用已聚合结果，避免重复全量解析与排序。

#### Scenario: repeated polling without file changes
- **WHEN** 客户端在短周期内重复调用 `timeline/history`
- **AND** run 审计文件签名未变化
- **THEN** 服务端 MUST 复用缓存聚合结果

### Requirement: terminal protocol history MUST converge to audit-only source
在 run 进入 terminal 后，RASP/FCMP 历史查询 MUST 以审计文件为唯一来源，避免 live 增量残留造成终态漂移。

#### Scenario: terminal run protocol history
- **GIVEN** run 状态已是 `succeeded|failed|canceled`
- **WHEN** 客户端查询 `protocol/history`（`stream=rasp|fcmp`）
- **THEN** 返回 MUST NOT 混合 live journal 事件
- **AND** `source` MUST 为 `audit`
