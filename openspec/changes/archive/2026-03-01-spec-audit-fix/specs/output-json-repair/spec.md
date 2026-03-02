# output-json-repair Specification

## Purpose
定义输出解析阶段的 deterministic generic repair 策略和 Schema-first 成功标准。

## MODIFIED Requirements

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
