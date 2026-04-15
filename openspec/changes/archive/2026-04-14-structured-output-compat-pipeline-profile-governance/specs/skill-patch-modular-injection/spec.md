## MODIFIED Requirements

### Requirement: 输出 schema 注入 MUST 动态可选
系统 MUST 在 output schema 存在且可解析时注入 schema 说明块，并且该说明块 MUST 来自 structured-output pipeline 选定的 prompt contract artifact。

#### Scenario: schema 可解析
- **WHEN** 发现有效 output schema
- **THEN** 注入 `### Output Schema Specification`
- **AND** 注入内容 MUST 使用当前 engine 通过 structured-output pipeline 解析出的 prompt contract artifact

#### Scenario: engine 需要 compat prompt contract
- **WHEN** 当前 engine profile 声明 prompt contract 使用 compatibility artifact
- **THEN** patch 注入 MUST 使用 compatibility summary
- **AND** 该 summary MUST 与命令行实际注入的 machine schema artifact 保持同一治理来源

#### Scenario: schema 缺失或无效
- **WHEN** output schema 缺失或解析失败
- **THEN** 跳过 schema 说明模块并继续其余 patch 注入
