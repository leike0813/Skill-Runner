## ADDED Requirements

### Requirement: RASP turn-complete event MUST carry structured turn stats
`agent.turn_complete` 事件 MUST 承载结构化统计信息，且数据 MUST 直接位于 `data` 顶层对象。

#### Scenario: gemini turn complete carries stats
- **GIVEN** Gemini 结构化输出包含 `stats`
- **WHEN** parser 产出回合结束语义并发布 RASP
- **THEN** `agent.turn_complete.data` MUST 直接包含 `stats` 对象内容
- **AND** 不得再嵌套 `data.details`

#### Scenario: codex/opencode turn complete carries normalized metrics
- **GIVEN** Codex `turn.completed` 含 `usage` 或 OpenCode `step_finish.part` 含 `cost/tokens`
- **WHEN** parser 产出回合结束语义并发布 RASP
- **THEN** `agent.turn_complete.data` MUST 直接承载对应结构化字段
- **AND** 事件类型与 RASP/FCMP 命名边界保持不变

### Requirement: Eventized run handle MUST be emitted for Gemini and iFlow
Gemini 与 iFlow 在可识别会话句柄时 MUST 发布 `lifecycle.run_handle`，用于即时持久化恢复句柄。

#### Scenario: gemini structured response includes session_id
- **GIVEN** Gemini 运行期批次 JSON 含 `session_id`
- **WHEN** parser 完成语义提取
- **THEN** 系统 MUST 发布 `lifecycle.run_handle` 且 `data.handle_id = session_id`

#### Scenario: iflow execution info includes session-id
- **GIVEN** iFlow 输出存在 `<Execution Info>` 且内层 JSON 含 `session-id`
- **WHEN** parser 提取 execution info
- **THEN** 系统 MUST 发布 `lifecycle.run_handle` 且 `data.handle_id = session-id`
