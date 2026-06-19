## MODIFIED Requirements

### Requirement: Engine upgrade tasks MUST target active engines only

系统 MUST 仅允许 active engines 参与 install/upgrade 任务。

#### Scenario: upgrade all excludes Gemini
- **WHEN** 客户端创建 all-engine upgrade task
- **THEN** task MUST target `codex`、`opencode`、`claude`、`qwen`
- **AND** MUST NOT target `gemini`

#### Scenario: single Gemini upgrade rejected
- **WHEN** 客户端请求 single-engine upgrade for `gemini`
- **THEN** 系统 MUST reject it as unsupported
