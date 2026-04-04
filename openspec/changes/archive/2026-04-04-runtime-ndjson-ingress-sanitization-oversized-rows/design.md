# runtime-ndjson-ingress-sanitization-oversized-rows Design

## Design Overview

本次 change 把超长 NDJSON 保护从 parser/live publisher 层提升到 subprocess stdout ingress。

核心设计分两部分：

1. `NdjsonIngressSanitizer`
   - 在 runtime 入口逐行维护 NDJSON 状态
   - 正常行直接透传
   - 超长行只保留 `4096` bytes 前缀，等待换行后做 repair 或 diagnostic substitution
2. 净化后 raw 单一真相
   - ingress sanitizer 的输出成为 `io_chunks`、`stdout.log`、live parser 与 strict replay 的共同输入
   - 原始超长 subprocess bytes 不再进入这些 runtime 审计面

这样可以在最上游切断超长 `tool_result` 对 runtime 热路径和后续物化结果的污染。

## Ingress Sanitization

- 仅对 NDJSON 引擎启用，目前范围为 `claude` / `codex` / `opencode`
- 仅对 `stdout` 启用；`stderr` 保持原语义，避免把 plain-text 错误输出误判为 NDJSON
- 阈值固定为 `4096` bytes
- 超限后：
  - 停止继续保留原始正文
  - 继续等待该逻辑行的换行
  - 换行后优先做 JSON repair
- repair 成功时：
  - 输出截断后的合法 JSON 单行
  - 发布 `RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED`
- repair 失败时：
  - 输出 runtime 生成的 diagnostic JSON 单行
  - 发布 `RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED`

## Sanitized Raw SSOT

对超长行而言，runtime raw 真相从“subprocess 原始 bytes”切换为“runtime 净化后的单行 JSON bytes”。

这意味着：

- `io_chunks.payload_b64` 对超长行保存的是净化后 bytes
- `stdout.log` / `raw_stdout` / live parser `text` 都与这份净化后 bytes 一致
- strict replay 只会看到净化后的行
- `raw_ref.byte_from/byte_to` 对超长行锚定净化后 raw，而非完整 subprocess 原文

该取舍是显式的：牺牲超长中间正文保真，换取 runtime 核心链路的可用性和一致性。

## Integration Boundaries

- `base_execution_adapter` 成为唯一 ingress 裁决点
- 现有 shared parser/live publisher 继续保留 parser-level overflow guard 作为防御性兜底
- 但在正常 ingress 已净化的路径上，shared parser 不应再看到原始超长行
- strict replay 沿用现有 `io_chunks` 读取接口，不改文件格式，只改变超长行的 payload 来源

## Compatibility

- 无外部 HTTP API 变化
- 无 `LiveParserEmission` / `RuntimeStreamParseResult` 结构变化
- 无 FCMP / RASP / chat 类型变化
- 新增的只是 runtime 诊断 code：
  - `RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED`
  - `RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED`
