## MODIFIED Requirements

### Requirement: request_input audit MUST capture first-attempt rendered prompt and effective spawn command
系统 MUST 在 `.audit/request_input.json` 记录首 attempt 的最终渲染 prompt 与实际执行命令信息，用于跨平台排障。

#### Scenario: first-attempt audit preserves native schema dispatch arguments
- **GIVEN** run 正在执行首个 Claude 或 Codex headless attempt
- **AND** internal `run_options` 提供 `__target_output_schema_relpath`
- **WHEN** runtime 完成最终执行命令确定
- **THEN** `.audit/request_input.json` 中的 `spawn_command_original_first_attempt` MUST include the injected native schema flag
- **AND** `spawn_command_effective_first_attempt` MUST include the same schema flag unless command normalization rewrites only the executable wrapper
