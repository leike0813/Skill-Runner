## ADDED Requirements

### Requirement: runner manifest MUST allow declaring final result filename

`assets/runner.json` 合同 MUST 允许 skill 显式声明最终结果 JSON 文件名，以便 runtime 在主路径失败时执行结果文件恢复。

#### Scenario: entrypoint.result_json_filename passes manifest validation
- **WHEN** `runner.json.entrypoint.result_json_filename` 为非空字符串
- **THEN** skill package manifest 校验必须通过

#### Scenario: omitted result_json_filename falls back to default naming
- **WHEN** `runner.json.entrypoint.result_json_filename` 未声明
- **THEN** skill package manifest 校验必须保持通过
- **AND** runtime 使用默认 `<skill-id>.result.json`
