## ADDED Requirements
### Requirement: ask_user 证据 MUST 高于 generic JSON repair
interactive 模式下，ask_user 证据 MUST 作为最高优先级门禁，generic JSON repair 不得覆盖其判定。

#### Scenario: ask_user yaml suppresses generic repair
- **WHEN** assistant 文本同时包含 `<ASK_USER_YAML>` 与可提取 JSON
- **THEN** 系统 MUST 优先判定为需要用户输入
- **AND** generic repair MUST NOT 将该回合改判为 soft completion

### Requirement: lifecycle MUST emit warnings for risky soft-completion inputs
系统 MUST 对会导致误判风险的 structured output 条件输出稳定 warning。

#### Scenario: permissive schema warning
- **WHEN** interactive 模式通过 soft completion 完成
- **AND** output schema 过宽松
- **THEN** 系统 MUST 记录 `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`

#### Scenario: extracted json invalid warning
- **WHEN** interactive 模式提取到标准化 JSON
- **AND** output schema 校验失败
- **THEN** 系统 MUST 记录 `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`
- **AND** run MUST 保持 `waiting_user`
