## ADDED Requirements

### Requirement: Prompt-facing output contract Markdown MUST NOT be materialized as a run audit artifact
系统 MUST 保留 canonical machine schema `.json` 作为 run-scoped audit truth，但 MUST NOT 再落盘 prompt-facing output contract Markdown artifact。

#### Scenario: output contract audit assets
- **WHEN** runtime 为 run materialize target output schema
- **THEN** `.audit/contracts/target_output_schema.json` MUST 存在
- **AND** `.audit/contracts/target_output_schema.md` MUST NOT 被创建

#### Scenario: compat output contract audit assets
- **WHEN** 某引擎需要 compat-translated machine schema
- **THEN** compat `.json` artifact MAY 被 materialize
- **AND** compat `.md` prompt artifact MUST NOT 被 materialize
