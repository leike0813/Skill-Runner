## ADDED Requirements

### Requirement: run detail RASP summary MUST render parsed JSON events
管理 UI Run Detail 的 RASP 摘要视图 MUST 能识别并渲染 `parsed.json` 事件。

#### Scenario: parsed json bubble summary
- **WHEN** RASP 行中存在 `event.type = parsed.json`
- **THEN** 页面摘要 MUST 展示至少 `stream` 与响应摘要（`response` 或 `summary`）
- **AND** 若存在 `session_id`，摘要 SHOULD 显示该值以便追踪会话
