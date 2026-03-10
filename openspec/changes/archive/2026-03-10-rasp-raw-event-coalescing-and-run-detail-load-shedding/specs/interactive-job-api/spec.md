## ADDED Requirements

### Requirement: management protocol history MUST support bounded result windows
管理端协议历史查询 MUST 支持可选 `limit` 参数以限制返回事件数量。

#### Scenario: default bounded window
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history` 且不传 `limit`
- **THEN** 服务端 MUST 返回最近窗口（默认 200 条）

#### Scenario: incremental bounded window
- **GIVEN** 客户端传入 `from_seq`
- **WHEN** 同时传入 `limit`
- **THEN** 服务端 MUST 保持增量语义并按 `limit` 进行上限截断

### Requirement: raw event payload MUST remain string-compatible after coalescing
RASP `raw.stdout/raw.stderr` 的 `data.line` 字段 MUST 保持 `string` 类型，允许多行块文本。

#### Scenario: coalesced raw stderr block
- **WHEN** 后端将多条连续 stderr 行归并
- **THEN** 事件类型仍为 `raw.stderr`
- **AND** `data.line` MUST be a string containing newline-separated content

### Requirement: live and audit raw transformations MUST share one canonicalization rule
运行期 live 发布与终态审计重建在 raw 分块上 MUST 复用同一 canonicalization 规则，避免前后观测结果漂移。

#### Scenario: same raw input observed in live and terminal views
- **WHEN** 同一 run 在运行期和终态分别读取 RASP raw 事件
- **THEN** raw 分块边界规则 MUST 一致
- **AND** 不得出现“仅 live 逐行拆分、终态分块”的双轨行为
