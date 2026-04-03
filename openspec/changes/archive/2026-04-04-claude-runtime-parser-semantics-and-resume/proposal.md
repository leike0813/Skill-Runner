# claude-runtime-parser-semantics-and-resume Proposal

## Summary

补齐 Claude interactive/runtime parser 的 session handle 提取、语义事件分类与 resume 契约收口。

## Motivation

Claude 当前已经接入 runtime，但还有两处行为没有对齐现有引擎：

- `system/init` 虽然带 `session_id`，parser 还没有把它作为稳定的 `run_handle` 主锚点收口
- `assistant/tool_use`、`user/tool_result`、`result` 的语义提取仍然偏浅，和 Codex / OpenCode 当前的 `process_type/classification` 风格不一致
- harness 侧对 Claude resume 仍保留旧的命令预期，没有跟现有 builder 的 `--resume <session-id>` 语义对齐

## Scope

- 完善 Claude runtime stream parser 的 `run_handle`、`assistant_messages`、`process_events`、`turn_markers`
- 将 Claude 的事件分类收口到 `tool_call` / `command_execution` 两类稳定分类
- 对齐 Claude resume 的 harness / regression 口径

## Non-Goals

- 不改变 Claude 的 `stream-json` 输出协议
- 不新增 HTTP API 或新的 runtime schema 字段
- 不为 Claude 发明一套独立于 Codex / OpenCode 的细粒度 taxonomy

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`
- `external-runtime-harness-cli`
