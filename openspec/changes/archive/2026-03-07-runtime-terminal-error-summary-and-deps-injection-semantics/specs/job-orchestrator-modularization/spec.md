## MODIFIED Requirements

### Requirement: Terminal lifecycle emission MUST carry failure summary when available
当 run 进入 `failed|canceled` 终态时，orchestrator MUST 在 `lifecycle.run.terminal` 的 payload 中携带稳定错误摘要（至少 `code`，可选 `message`）。

#### Scenario: failed terminal lifecycle includes code and summary
- **WHEN** run 收敛到 `failed`
- **THEN** `lifecycle.run.terminal.data.status=failed`
- **AND** payload SHOULD 包含 `code`
- **AND** payload SHOULD 包含长度受控的 `message` 摘要

#### Scenario: FCMP terminal prefers lifecycle summary
- **WHEN** FCMP 从 orchestrator terminal lifecycle 翻译 terminal 状态
- **THEN** `conversation.state.changed.data.terminal.error` MUST 优先使用 `lifecycle.run.terminal` 的 `code/message` 摘要
