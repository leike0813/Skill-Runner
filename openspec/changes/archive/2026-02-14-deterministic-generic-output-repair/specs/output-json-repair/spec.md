## ADDED Requirements

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
