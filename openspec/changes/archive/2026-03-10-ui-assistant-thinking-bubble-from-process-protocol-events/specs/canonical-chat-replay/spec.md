## ADDED Requirements

### Requirement: chat replay contract MUST include assistant_process kind
chat replay 合同 MUST 扩展 `assistant_process` kind，用于承载 assistant 思考过程。

#### Scenario: schema validation accepts assistant_process
- **GIVEN** chat replay 事件 `role=assistant` 且 `kind=assistant_process`
- **WHEN** 执行 schema 校验
- **THEN** 该事件 MUST 通过校验

### Requirement: derivation rules MUST map FCMP process events to assistant_process
chat replay 派生规则 MUST 定义 FCMP 过程事件到 `assistant_process` 的映射。

#### Scenario: derive process kinds from FCMP
- **GIVEN** FCMP 事件类型为 `assistant.reasoning`
- **WHEN** 执行 chat replay 派生
- **THEN** 生成事件 MUST 为 `role=assistant` + `kind=assistant_process`
