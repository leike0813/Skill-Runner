# ndjson-live-overflow-repair-and-resync Proposal

## Summary

为共享 NDJSON live parser 与 live raw publisher 增加超长单行保护。当单条未闭合 NDJSON 行超过 `4 KiB` 时，系统不再无限累积原始正文，而是保留受限前缀、在换行或进程退出时将该行修复成合法 JSON 对象，再继续送入现有 parser，以保住事件类型与关联标识。

## Motivation

Claude / OpenCode 的 verbose NDJSON 输出会在 `tool_result`、`skill` 输出等场景中产生超长单行。现有 live parser 与 raw publisher 都按“整行 + 换行”缓冲，且每个 chunk 都会反复拼接并扫描增长中的大字符串。这会导致：

- live 事件长期静默，观测页面停更
- 单进程 uvicorn 事件循环被大字符串热路径拖慢
- 即使 `io_chunks` 仍在持续写入，live 语义也无法及时恢复

直接丢弃超长行会损失 `type`、`tool_use_id`、`session_id` 等关键语义，因此本 change 采用“截断正文 + 修复 JSON + 保住语义”的方式。

## Scope

- 为共享 NDJSON 行缓冲增加 `4 KiB` overflow guard
- 增加通用 JSON 截断修复器
- 让 parser 与 raw publisher 共用同一套 overflow / repair / resync 机制
- 为 repaired / unrecoverable overflow 增加 live diagnostic warning

## Non-Goals

- 不改变 `io_chunks` 原始审计采集方式
- 不移除 Claude 的 `--verbose`
- 不修改 Claude / Codex / OpenCode 的引擎专属语义映射规则
- 不新增 FCMP / RASP 事件类型

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
