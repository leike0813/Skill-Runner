## ADDED Requirements

### Requirement: 系统 MUST 使用模块化 skill patch 注入流水线
系统 MUST 基于统一 patch plan 进行 `SKILL.md` 注入，而非散落硬编码拼接。

#### Scenario: 注入计划生成
- **WHEN** 运行时准备 patch skill
- **THEN** 系统生成有序模块列表并按顺序注入

### Requirement: 模板 MUST 作为注入文案单一来源
系统 MUST 从 `server/assets/templates` 加载固定注入模板。

#### Scenario: 模板读取
- **WHEN** 构建 patch 内容
- **THEN** 读取 runtime enforcement/output format/artifact/mode 模板
- **AND** 缺失模板时 fail fast

### Requirement: 动态 output schema 注入 MUST 可选且稳定
系统 MUST 在 output schema 可用时注入 `### Output Schema Specification`，不可用时跳过且不中断主流程。

#### Scenario: schema 可用
- **WHEN** skill 提供有效 output schema
- **THEN** 注入动态 schema 说明块

#### Scenario: schema 缺失
- **WHEN** skill 无 output schema 或解析失败
- **THEN** 跳过该模块并继续注入其余模块
