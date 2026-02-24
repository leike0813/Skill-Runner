# skill-patch-modular-injection Specification

## Purpose
定义 runtime skill patch 的模块化注入模型、模板来源与幂等行为。

## Requirements

### Requirement: 系统 MUST 以模块化计划驱动 skill patch
系统 MUST 通过统一 patch plan 生成注入模块列表并依序执行。

#### Scenario: 模块计划生成
- **WHEN** 运行时调用 skill patch
- **THEN** 系统生成可审计的模块顺序和内容

### Requirement: 模板 MUST 是注入文案唯一来源
系统 MUST 从 `server/assets/templates` 读取固定模板内容。

#### Scenario: 模板读取失败
- **WHEN** 任一必需模板缺失
- **THEN** 系统 fail fast 并返回明确错误

### Requirement: 输出 schema 注入 MUST 动态可选
系统 MUST 在 output schema 存在且可解析时注入 schema 说明块。

#### Scenario: schema 可解析
- **WHEN** 发现有效 output schema
- **THEN** 注入 `### Output Schema Specification`

#### Scenario: schema 缺失或无效
- **WHEN** output schema 缺失或解析失败
- **THEN** 跳过 schema 说明模块并继续其余 patch 注入

### Requirement: 注入 MUST 保持幂等
系统 MUST 通过模块 marker 防止重复注入。

#### Scenario: 重复 patch
- **WHEN** 对同一 `SKILL.md` 连续执行 patch
- **THEN** 每个模块最多出现一次
