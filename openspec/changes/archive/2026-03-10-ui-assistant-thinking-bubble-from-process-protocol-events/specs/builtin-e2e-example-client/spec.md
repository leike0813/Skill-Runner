## ADDED Requirements

### Requirement: E2E chat renderer MUST group assistant_process events into collapsible thinking bubbles
E2E 对话区 MUST 将连续的 `assistant_process` 条目聚合为单个可折叠思考气泡。

#### Scenario: collapsed thinking bubble shows latest process line
- **GIVEN** 连续收到多条 `assistant_process`
- **WHEN** 思考气泡处于折叠状态
- **THEN** UI MUST 仅显示最后一条过程消息

### Requirement: E2E renderer MUST dedupe promoted/final content
E2E 对话区 MUST 在 `assistant_final` 到达时移除已提升的过程条目，避免重复渲染。

#### Scenario: final dedupe by message_id then normalized text
- **GIVEN** 已渲染思考条目
- **AND** 后续收到 `assistant_final`
- **WHEN** `message_id` 可用
- **THEN** UI MUST 优先按 `message_id` 删除对应过程条目
- **AND** 若 `message_id` 缺失，MUST 在同 attempt 按规范化文本精确匹配删除
