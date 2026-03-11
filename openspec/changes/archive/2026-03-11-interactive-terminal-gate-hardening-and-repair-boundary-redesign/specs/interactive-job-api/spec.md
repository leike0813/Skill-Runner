## ADDED Requirements
### Requirement: interactive API diagnostics MUST surface gate-hardening warnings
interactive API 响应与观测接口 MUST 暴露新的 gate-hardening warning / diagnostic。

#### Scenario: result and diagnostics expose schema-invalid waiting warning
- **WHEN** 当前回合提取到 JSON 但 output schema 校验失败
- **THEN** result / meta / protocol diagnostics 中 MUST 包含 `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`

#### Scenario: result and diagnostics expose permissive schema warning
- **WHEN** 当前回合以 soft completion 成功
- **AND** output schema 被判定为过宽松
- **THEN** result / meta / protocol diagnostics 中 MUST 包含 `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`
