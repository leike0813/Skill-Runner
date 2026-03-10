## ADDED Requirements

### Requirement: protocol history MUST allow Gemini parsed JSON events
管理端协议历史中的 RASP 流 MUST 支持 `parsed.json` 事件类型，用于承载 Gemini 的整段 JSON 解析结果。

#### Scenario: parsed JSON event in RASP history
- **WHEN** Gemini parser 从 stdout/stderr 成功解析出整段 JSON
- **THEN** `GET /v1/management/runs/{request_id}/protocol/history?stream=rasp` 返回中 MAY 包含 `event.type = parsed.json`
- **AND** 该事件 `data` MUST 至少包含 `stream`

### Requirement: raw line payload MUST remain string-compatible after parser coalescing
Gemini parser 归并后的 `raw.stdout/raw.stderr` 事件 `data.line` MUST 仍保持字符串（可多行）。

#### Scenario: coalesced stderr block
- **WHEN** 连续 stderr 行被归并为块
- **THEN** 事件类型仍为 `raw.stderr`
- **AND** `data.line` MUST be a string containing newline-separated content
