## MODIFIED Requirements

### Requirement: API 链路参数合并规则 MUST 稳定可预期
系统 MUST 定义 API 链路命令参数的稳定合并顺序，并保证显式调用参数优先级高于 Profile 默认参数。

#### Scenario: Claude headless profile defaults use JSON output mode
- **WHEN** Claude API 链路使用 profile 默认参数构建 start 或 resume 命令
- **THEN** profile 默认参数 MUST include `--output-format json`
- **AND** 该默认输出模式 MUST remain compatible with later native schema flag injection

#### Scenario: passthrough command bypasses profile-native schema injection
- **WHEN** builder receives explicit passthrough CLI args
- **THEN** command construction MUST preserve passthrough ownership
- **AND** it MUST NOT append native output schema flags automatically
