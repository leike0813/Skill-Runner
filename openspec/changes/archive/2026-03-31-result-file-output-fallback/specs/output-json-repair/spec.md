## ADDED Requirements

### Requirement: 系统 MUST 在主路径失败后尝试结果文件兜底恢复

当 deterministic generic repair 与主路径结构化输出提取无法得到合法最终结果时，系统 MUST 可在 run 工作目录内尝试恢复结果文件。

#### Scenario: stdout 缺失时由结果文件恢复成功
- **GIVEN** run `exit_code == 0`
- **AND** stdout/stream 未能提供可解析的最终 JSON
- **AND** `run_dir` 中存在合法的 `<skill-id>.result.json`
- **WHEN** lifecycle 执行终态标准化
- **THEN** 系统必须使用该文件内容作为最终 `output_data`
- **AND** run 状态为成功
- **AND** 结果包含 warning `OUTPUT_RECOVERED_FROM_RESULT_FILE`

#### Scenario: stdout JSON schema 非法时由结果文件恢复成功
- **GIVEN** run `exit_code == 0`
- **AND** stdout/stream 中提取出的 JSON 未通过 `output.schema`
- **AND** `run_dir` 中存在通过 schema 的结果文件
- **WHEN** lifecycle 执行终态标准化
- **THEN** 系统必须改用结果文件内容作为最终 `output_data`
- **AND** run 状态为成功

#### Scenario: 结果文件非法时保持失败
- **GIVEN** run `exit_code == 0`
- **AND** 主路径未得到合法最终 JSON
- **AND** 命中的结果文件 JSON 非法或不满足 `output.schema`
- **WHEN** lifecycle 执行终态标准化
- **THEN** run 状态必须保持失败
- **AND** 结果必须包含对应 warning
