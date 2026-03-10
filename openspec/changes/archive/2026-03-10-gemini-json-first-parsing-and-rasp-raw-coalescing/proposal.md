## Why

Gemini 在高频错误场景下会产生大量 stderr 行，当前链路容易把这些行直接转为大量 `raw.stderr` 事件，导致 RASP 与管理 UI 负载上升。  
同时，Gemini stdout/stderr 中常见整段 JSON 输出（含 `session_id` / `response`）没有被优先结构化表达，影响可观测性。

## What Changes

- Gemini parser 升级为 batch-first：优先按整段 JSON 解析 stdout/stderr，再提取关键字段。
- 新增 RASP 事件类型 `parsed.json`（Gemini 先落地）承载结构化解析结果。
- Gemini raw 行在 parser 阶段做分块归并，减少事件爆炸。
- 管理 UI Run Detail 增加 `parsed.json` 摘要展示。
- API 文档补充 `parsed.json` 与 raw 多行块语义。

## Impact

- Public API 路由无新增/删除。
- `protocol/history` 响应语义扩展：RASP 可能包含 `parsed.json`，`raw.*.data.line` 仍为字符串（可多行）。
