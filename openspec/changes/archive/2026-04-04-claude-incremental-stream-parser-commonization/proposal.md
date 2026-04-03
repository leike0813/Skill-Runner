# claude-incremental-stream-parser-commonization Proposal

## Summary

将 Claude runtime parser 从 terminal-only semantic publish 改为真正的增量流式 parser，并抽取共享的 NDJSON live session base，让 Claude / Codex / OpenCode 收口到同一内部 live parsing 抽象。

## Motivation

当前 Claude parser 虽然已经具备 runtime 语义提取能力，但 live publish 仍通过 `live_semantic_on_finish_only = True` 在进程退出后一次性回放语义事件。这与 runtime contract 中“parser live session 可在执行期间增量吐出语义事件”的要求不一致，也导致 Claude 的 active SSE 时序滞后于 Codex / OpenCode。

同时，Codex / OpenCode 已分别实现 NDJSON 增量 live session，但两者在分流、尾部 buffer、按行切分和 byte offset 维护上存在重复逻辑，后续扩展 Claude 时会继续复制相同模式。

## Scope

- 为 NDJSON 引擎新增共享 live session base
- 将 Claude 改为真实增量 live parser
- 将 Codex / OpenCode 迁移到共享 NDJSON live session base
- 保持 `LiveParserEmission` / `RuntimeStreamParseResult` / FCMP / RASP 事件形状不变

## Non-Goals

- 不迁移 Gemini / iFlow 到新的 NDJSON live session base
- 不修改 Claude 的 batch `parse()` / `parse_runtime_stream()` 结果形状
- 不调整 auth detection 规则、resume contract、命令构造或 UI/SSE 对外接口

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
