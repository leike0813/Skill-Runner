## ADDED Requirements

### Requirement: Qwen runtime parser MUST conform to the shared adapter runtime contract
Qwen parser 语义 MUST 作为共享 adapter runtime contract 的一部分定义，而不是通过独立 qwen parser capability 单独维护。

#### Scenario: qwen runtime stream parsing uses shared contract fields
- **WHEN** Qwen 解析 `stream-json` NDJSON 运行时输出
- **THEN** parser MUST 提取 `system/subtype=init` 作为 `session_id` / `run_handle` 候选
- **AND** 它 MUST 提取 `assistant.message.content[].type=text` 为 `assistant_messages`
- **AND** 它 MUST 提取 `thinking`、`tool_use`、`tool_result` 为 `process_events`
- **AND** 它 MUST 提取 `result` 作为 turn-complete 语义与最终文本候选

#### Scenario: qwen live parser remains stdout and pty scoped
- **WHEN** Qwen live parser session 增量处理 NDJSON
- **THEN** live session MUST 接受 `stdout` 与 `pty`
- **AND** 它 MUST 为 `run_handle`、`turn_marker`、`assistant_message`、`process_event` 发出共享 emission
- **AND** 普通 `stderr` auth banner MUST NOT 被当作 live semantic event 处理

### Requirement: Adapter profile MAY declare UI shell config assets for session-local security
支持 UI shell 的 adapter profile MUST 能声明 session-local config 资产与目标路径，使安全限制通过共享 runtime contract 装配，而不是依赖 engine-specific capability。

#### Scenario: qwen adapter profile resolves ui shell config assets
- **WHEN** runtime 读取 qwen adapter profile 的 `ui_shell.config_assets`
- **THEN** profile MUST 能解析 default、enforced、settings schema 与 target relpath
- **AND** target relpath MUST 指向 `.qwen/settings.json`
