# runtime-utf8-stream-decoding-integrity Proposal

## Summary

修复运行时 `stdout` / `stderr` 的 UTF-8 编码漂移，让 `io_chunks`、`stdout/stderr.log`、live parser 输入和 strict replay 输入重新共享同一份文本真相，不再因为 `1024`-byte chunk 边界把合法多字节字符拆坏并写入伪造的 `�`。

## Motivation

当前运行时热路径会对每个原始 chunk 单独执行 `decode("utf-8", errors="replace")`。这会导致：

- `stdout/stderr.log` 与 `io_chunks` 的原始字节流不再一致
- live parser 看到的文本和 raw bytes 不再对应
- strict replay 会再次把跨 chunk 的 UTF-8 字符拆坏
- `raw_ref.byte_from/byte_to` 对应的日志文本发生漂移

该问题不会改变 `io_chunks` 作为原始字节真相源的角色，但会持续污染所有基于文本的审计、重放和语义解析。

## Scope

- 在 execution 热路径中改用增量 UTF-8 解码
- 在 strict replay 中改用基于 `io_chunks` 的跨 chunk 增量解码
- 抽出共享 decoder helper，避免 execution 与 replay 各写一套状态机
- 为跨 chunk 合法 UTF-8 和真实无效字节补充回归测试

## Non-Goals

- 不修改 `io_chunks` 文件格式
- 不改 `LiveRuntimeEmitter` 为 bytes-first
- 不改变 `raw_ref.byte_from/byte_to` 的字节语义
- 不在本次 change 中顺手修 terminal fallback / dispatch / protocol metrics 收尾异常

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
