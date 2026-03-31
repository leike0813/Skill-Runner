# output-json-repair Specification

## Purpose
定义输出解析阶段的 deterministic generic repair 策略和 Schema-first 成功标准。

## Requirements
### Requirement: 系统 MUST 在输出解析阶段执行 deterministic generic repair
当引擎最终输出不是严格 JSON 时，系统 MUST 尝试可预测、无语义猜测的通用修复。

#### Scenario: Code Fence 修复
- **WHEN** 输出文本包含 ```json ... ``` 代码块
- **THEN** 系统应剥离 fence 并尝试解析 JSON

#### Scenario: Envelope Response 修复
- **WHEN** 输出为 envelope JSON 且业务内容位于 `response` 字段
- **THEN** 系统应提取 `response` 文本并继续解析

#### Scenario: First JSON Object 修复
- **WHEN** 输出包含噪声文本与单个 JSON 对象
- **THEN** 系统应提取首个 JSON 对象并尝试解析

### Requirement: 系统 MUST 维持 Schema-first 成功标准
repair 后结果 MUST 通过 `output.schema` 才可标记成功。

#### Scenario: Repair 后 schema 通过
- **WHEN** repair 产物通过 output schema 校验
- **THEN** run 状态为成功
- **AND** 结果标记 `repair_level=deterministic_generic`
- **AND** 结果包含 warning `OUTPUT_REPAIRED_GENERIC`

#### Scenario: Repair 后 schema 失败
- **WHEN** repair 后仍不满足 output schema
- **THEN** run 状态保持失败
- **AND** 返回结构化解析/校验错误信息

### Requirement: Repair-success 结果 MUST 可缓存
对于 repair 后成功且 schema 通过的结果，系统 MUST 允许写入 cache。

#### Scenario: Repair-success 缓存
- **WHEN** run 通过 deterministic repair 达到 success
- **THEN** 系统记录 cache entry
- **AND** 后续相同请求可命中该结果

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
