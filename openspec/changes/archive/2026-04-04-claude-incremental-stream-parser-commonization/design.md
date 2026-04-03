# claude-incremental-stream-parser-commonization Design

## Design Overview

本次 change 分两层实现：

1. `server/runtime/adapter/common/live_stream_parser_common.py`
   - 提供共享 NDJSON live session base
   - 负责 `stdout` / `pty` 分流、split chunk 尾部 buffer、按换行切分、byte offset / `raw_ref` 维护
   - 仅在完整 NDJSON 行上尝试 `json.loads()`
2. 引擎专属 row handler
   - Claude / Codex / OpenCode 各自保留自己的 payload 语义提取
   - live session 只负责把单行 payload 转为 `LiveParserEmission`

## Shared NDJSON Live Session Base

- 只消费声明允许的流（本次为 `stdout` / `pty`）
- 维护每个流的：
  - 当前尾部文本 buffer
  - 当前尾部起始 byte offset
- `feed()` 在完整行边界上：
  - 计算稳定 `raw_ref`
  - 忽略空行
  - 忽略非 JSON 行或非 object payload
  - 将 `(payload, raw_ref, stream)` 交给引擎 row handler
- `finish()` 不执行 batch backfill，也不尝试消费未闭合尾部

## Claude Live Semantics

- `system/init`
  - 首次有效 `session_id` 立即发 `run_handle`
  - 首次 `system/init` 立即发 `turn_marker:start`
- `assistant.message.content[type=text]`
  - 按出现顺序立即发 `assistant_message`
- `assistant.message.content[type=tool_use]`
  - 立即发 `process_event`
  - 分类与 summary/details 逻辑保持与当前 batch parser 一致
- `user.message.content[type=tool_result]`
  - 立即发 `process_event`
  - 继续沿用 `tool_use_id` 与前序 `tool_use` 关联
- `result`
  - 若 `result.result` 有文本，先发 `assistant_message`
  - 再发 `turn_marker:complete`
  - 最后发 `turn_completed`

Claude live 语义顺序以实际 stream-json 行顺序为准，不再等待 batch materialization。

## Codex / OpenCode Migration

- 两者继续保留现有 batch `parse_runtime_stream()` 逻辑
- 仅将 live session 的 NDJSON 基础设施迁移到共享 base
- 保持现有 turn / step slicing、assistant/process 提取、marker/completion 行为不变

## Compatibility

- 不新增新的 `LiveParserEmission.kind`
- 不新增新的 `RuntimeStreamParseResult` 字段
- 不改变 FCMP / RASP 事件名与载荷结构
- 唯一允许的可观察变化是 Claude 语义事件发布时间从 process exit 前移到运行中
