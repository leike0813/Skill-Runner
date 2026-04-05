## MODIFIED Requirements

### Requirement: chat replay contract MUST include assistant_process kind
chat replay 合同 MUST 同时支持 `assistant_process` 与 `assistant_message` kind，用于分别承载真正的 assistant 过程语义和非终态 agent 文本。

#### Scenario: schema validation accepts assistant process and message kinds
- **GIVEN** chat replay 事件 `role=assistant`
- **WHEN** 执行 schema 校验
- **THEN** `kind=assistant_process` MUST 通过校验
- **AND** `kind=assistant_message` MUST 通过校验

### Requirement: derivation rules MUST map FCMP process events to assistant_process
chat replay 派生规则 MUST 将 FCMP 过程事件映射为 `assistant_process`，并将非终态 agent message 映射为 `assistant_message`。

#### Scenario: derive process and intermediate kinds from FCMP
- **GIVEN** FCMP 事件类型为 `assistant.reasoning`
- **WHEN** 执行 chat replay 派生
- **THEN** 生成事件 MUST 为 `role=assistant` + `kind=assistant_process`

#### Scenario: derive intermediate message from FCMP
- **GIVEN** FCMP 事件类型为 `assistant.message.intermediate`
- **WHEN** 执行 chat replay 派生
- **THEN** 生成事件 MUST 为 `role=assistant` + `kind=assistant_message`
