## MODIFIED Requirements

### Requirement: Adapter MUST 提供统一 runtime 流解析接口

系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types），并暴露可供 auth detection 使用的原始材料。

#### Scenario: Claude `type=result` defaults to completion-only semantics

- **GIVEN** Claude runtime stream contains a terminal `{"type":"result"}` row
- **WHEN** adapter 解析该 runtime 流
- **THEN** 该 `result` 行 MUST 继续产出 turn completion 语义与 completion metadata
- **AND** `result.result` MUST NOT 默认进入 `assistant_messages`

#### Scenario: Claude `result.result` may become a fallback assistant message only in narrow conditions

- **GIVEN** Claude runtime stream contains a terminal `{"type":"result"}` row
- **AND** 当前 turn 没有真实 assistant body message
- **AND** 该 `result` 行没有 `structured_output`
- **AND** `result.result` 非空
- **WHEN** adapter 解析该 runtime 流
- **THEN** adapter MAY 产出一条 fallback assistant message
- **AND** 该消息 MUST 带有 `details.source = "claude_result_fallback"`
