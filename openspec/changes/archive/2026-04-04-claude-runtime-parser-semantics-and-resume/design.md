# claude-runtime-parser-semantics-and-resume Design

## Design Overview

本次 change 的实现重点是让 Claude parser 与现有 Codex / OpenCode 的运行语义保持同一风格：

- `run_handle` 从结构化流事件稳定提取
- `process_type/classification` 只保留少量稳定值
- Claude 特有差异放进 `details`

## Parser Semantics

### Session bootstrap

- `system/init.session_id` 作为 Claude session handle 的首选来源
- parser 首次看到有效 `session_id` 时生成 `run_handle`
- `system/init` 同时视为 turn start 的可靠锚点之一

### Process events

- `assistant.thinking`
  - MUST map to `reasoning`
  - thinking 文本进入 `text`
  - Claude-specific block type 细节进入 `details.item_type = thinking`
- `assistant.tool_use`
  - `Bash` / `grep` -> `command_execution`
  - 其他工具 -> `tool_call`
- `user.tool_result`
  - 优先通过 `tool_use_id` 关联前序 `tool_use`
  - 分类继续沿用前序 `tool_use` 的 `process_type`
  - success/error、原始 `tool_use_result`、工具名等细节都放入 `details`

### Result events

- `result` 保持 turn complete 语义
- `subtype=success` + `structured_output` 仍然是结构化终态主路径
- `result.result` 的可读文本进入 `assistant_messages`

## Resume Contract

- Claude interactive resume 的统一命令语义为：
  - `claude --resume <session-id> ...`
- builder 维持现有实现
- harness 与回归测试统一对齐到这一口径，不再保留旧的 `exec resume` 断言
