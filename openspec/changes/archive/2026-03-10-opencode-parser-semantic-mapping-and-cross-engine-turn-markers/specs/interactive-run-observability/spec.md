## ADDED Requirements

### Requirement: RASP MUST support cross-engine turn markers
RASP 审计流 MUST 支持通用回合标记事件 `agent.turn_start` 与 `agent.turn_complete`，并保持引擎无关语义。

#### Scenario: codex/opencode explicit markers
- **GIVEN** Codex 或 OpenCode 解析到显式 turn 边界事件
- **WHEN** 事件进入 live publisher
- **THEN** 系统 MUST 发布 `agent.turn_start` 与 `agent.turn_complete`
- **AND** 事件 SHOULD 继承对应源行 `raw_ref`

#### Scenario: gemini/iflow implicit turn start
- **GIVEN** Gemini 或 iFlow attempt 子进程已启动
- **WHEN** live publisher 收到 process started 信号
- **THEN** 系统 MUST 立即发布一次 `agent.turn_start`
- **AND** 不得依赖首条 stdout/stderr 输出

### Requirement: Semantic-hit rows MUST suppress duplicated raw rows
当 parser 已提取语义事件且具备 `raw_ref` 时，重叠区间的 raw 行 MUST 被抑制。

#### Scenario: opencode tool_use mapped to process_event
- **GIVEN** OpenCode NDJSON 行命中 `tool_use` 语义映射
- **WHEN** live pipeline 同时处理 raw 行与 process_event
- **THEN** 对应 `raw_ref` 区间的 `raw.stdout/raw.stderr` MUST NOT 再次发布

### Requirement: RASP MUST expose lifecycle run handle for eventized engines
当引擎输出中包含可识别的 run/session 句柄时，RASP MUST 发布 `lifecycle.run_handle` 事件并携带 `data.handle_id`。

#### Scenario: codex thread started emits run handle
- **GIVEN** Codex 输出 `thread.started` 且包含 `thread_id`
- **WHEN** parser 处理该行并进入 live publisher
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** 事件 `data.handle_id` MUST 等于该 `thread_id`

#### Scenario: opencode step start emits run handle
- **GIVEN** OpenCode 输出 `step_start` 且包含 `sessionID`
- **WHEN** parser 处理该行并进入 live publisher
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** 同一源行 MAY 同时发布 `agent.turn_start`

### Requirement: run handle change MUST be observable
当同一 run 的 handle 发生变更时，系统 MUST 覆盖存储并发布可观测诊断告警。

#### Scenario: handle changed during later attempt
- **GIVEN** run 已持久化 handle `A`
- **WHEN** live publisher 再次发布 `lifecycle.run_handle` 且值为 `B`（`B != A`）
- **THEN** 系统 MUST 将 run handle 更新为 `B`
- **AND** MUST 发布 `diagnostic.warning`，`data.code = RUN_HANDLE_CHANGED`
