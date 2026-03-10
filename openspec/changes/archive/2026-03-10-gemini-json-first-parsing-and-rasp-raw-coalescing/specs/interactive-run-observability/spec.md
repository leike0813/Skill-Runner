## ADDED Requirements

### Requirement: Gemini parser MUST prefer batch JSON parse for runtime streams
Gemini runtime parser MUST 先尝试将当前 stdout/stderr 批次作为整段 JSON 解析，再回退到行级/fenced JSON 路径。

#### Scenario: stdout batch JSON detected
- **WHEN** stdout 包含可解析 JSON 文档
- **THEN** parser MUST 提取 `session_id` 与 `response`（若存在）
- **AND** parser MUST 产出结构化 payload 供 RASP `parsed.json` 事件使用

### Requirement: Gemini raw rows MUST be coalesced before RASP emission
Gemini parser 输出的 raw 行 MUST 在进入 RASP 构建前执行归并，避免逐行爆炸。

#### Scenario: large stderr burst
- **GIVEN** Gemini stderr 在单次 attempt 中产生大量连续文本行
- **WHEN** parser 输出 raw 行
- **THEN** raw 行 MUST 被归并为有限数量的块
- **AND** 行归并后的上下文顺序 MUST 保持稳定
