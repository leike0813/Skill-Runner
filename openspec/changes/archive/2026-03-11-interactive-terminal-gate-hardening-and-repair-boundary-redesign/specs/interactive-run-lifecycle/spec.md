## ADDED Requirements
### Requirement: interactive 终态门禁 MUST 先判 ask_user 再判 soft completion
interactive 模式 MUST 先消费 done marker 与 ask-user 证据，再允许 structured output 走 soft completion。

#### Scenario: ask_user 证据阻止 soft completion
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 命中 `<ASK_USER_YAML>` 或显式 ask_user 证据
- **THEN** run MUST 进入 `waiting_user`
- **AND** 不得因为 output schema 通过而直接进入 `succeeded`

#### Scenario: extracted JSON but schema invalid keeps waiting
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 成功提取标准化 JSON
- **AND** output schema 校验失败
- **THEN** run MUST 进入 `waiting_user`
- **AND** 不得直接进入 `failed`

#### Scenario: no ask_user and no JSON also keeps waiting
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 未提取到标准化 JSON
- **THEN** run MUST 进入 `waiting_user`

### Requirement: interactive soft completion MUST require valid structured output
interactive 模式下的 soft completion MUST 仅在标准化 JSON、schema 校验和 artifact 修复同时成立时触发。

#### Scenario: soft completion requires schema and artifact validation
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 提取到标准化 JSON
- **AND** output schema 校验通过
- **AND** best-effort artifact 路径修复后仍成立
- **THEN** run MAY 进入 `succeeded`
