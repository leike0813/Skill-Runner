# runtime-ndjson-ingress-sanitization-oversized-rows Proposal

## Summary

将超长 NDJSON 保护前移到 runtime ingress。对于 Claude、Codex、OpenCode 这类 NDJSON 引擎的超长 stdout 逻辑行，系统不再把原始完整正文写入 `io_chunks`、`stdout.log`、live parser 或 strict replay，而是在入口处保留受限前缀、修复为合法 JSON 单行后再继续下游处理。

## Motivation

此前的 parser-level overflow repair 只能避免 live parser 长时间持有巨型行，但超长 `tool_result` 原文仍会进入：

- `io_chunks`
- `stdout.log`
- `raw_stdout`
- strict replay 输入

这会继续污染 runtime 的核心物化面，并放大后续的 replay、history、raw_ref 对齐和 UI 观测异常。现有问题已表明，对于这类超长 NDJSON 行，保住业务语义远比保住原始中间正文更重要。

## Scope

- 为 NDJSON 引擎的 stdout 读取热路径增加 ingress sanitizer
- 将超长逻辑行的 runtime raw 真相切换为“修复后的截断 JSON 行”
- 让 `io_chunks`、`stdout.log`、live parser、strict replay 全部消费同一份净化后文本
- 为 sanitized / substituted overflow 增加 runtime 诊断

## Non-Goals

- 不改变非 NDJSON 引擎的 stdout/stderr 路径
- 不修改 `io_chunks` JSONL row 形状
- 不修改 FCMP / RASP / chat 事件类型
- 不顺手修 terminal fallback、result-file fallback 或其它收尾异常

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
