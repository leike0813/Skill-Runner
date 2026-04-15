## ADDED Requirements

### Requirement: Structured output governance MUST define canonical truth and engine-effective transport separately
系统 MUST 将 canonical target output schema 与 engine transport compat schema 分离治理。

#### Scenario: canonical schema remains SSOT
- **WHEN** runtime materializes target output schema
- **THEN** canonical `.audit/contracts/target_output_schema.json` MUST remain the only machine truth
- **AND** compat schema MUST 被视为 engine transport artifact，而不是 canonical truth

### Requirement: Structured output pipeline MUST render prompt contract text from the engine-effective schema
系统 MUST 从 engine-effective schema 渲染最终 prompt contract 文本，确保 CLI schema 注入与 agent-visible contract 不漂移。

#### Scenario: render prompt contract for compat engine
- **WHEN** 某引擎启用 compat translate
- **THEN** prompt contract text MUST 从 compat schema 派生
- **AND** canonical schema 的差异 MUST 由 pipeline 负责吸收，而不是由下游模板自行解释

#### Scenario: render prompt contract for canonical engine
- **WHEN** 某引擎未启用 compat translate
- **THEN** prompt contract text MUST 直接从 canonical schema 派生
