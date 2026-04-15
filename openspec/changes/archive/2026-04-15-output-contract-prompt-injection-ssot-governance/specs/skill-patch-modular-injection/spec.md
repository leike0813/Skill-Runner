## MODIFIED Requirements

### Requirement: 输出 schema 注入 MUST 动态可选
系统 MUST 在 output schema 存在且可解析时注入单一的动态 output contract details 模块，并将该模块作为 runtime `SKILL.md` 中唯一的字段级文本合同来源。

#### Scenario: schema 可解析
- **WHEN** 发现有效 output schema
- **THEN** 系统 MUST 注入 `### Output Contract Details`
- **AND** 该模块 MUST 由统一动态 builder 生成
- **AND** 该模块 MUST 包含字段表、artifact 字段说明与示例

#### Scenario: schema 缺失或无效
- **WHEN** output schema 缺失或解析失败
- **THEN** 系统 MUST 跳过动态 contract details 模块
- **AND** 系统 MUST 继续其余 patch 注入

## ADDED Requirements

### Requirement: Runtime SKILL patch MUST use a fixed composition order
系统 MUST 按固定顺序组合 runtime `SKILL.md` 注入模块，避免静态模板与动态合同重复表达同一语义。

#### Scenario: runtime skill patch composition
- **WHEN** 运行时为 skill 生成 patch plan
- **THEN** 注入顺序 MUST 为 Runtime Enforcement → Runtime Output Overrides → Output Format Contract → Output Contract Details → Execution Mode
- **AND** Execution Mode 模块 MUST 出现在动态 contract details 之后

### Requirement: Interactive mode patch MUST express policy only
`patch_mode_interactive.md` MUST 仅表达 interactive 行为策略，不得重复 pending 分支的字段级合同说明。

#### Scenario: interactive mode patch rendering
- **WHEN** 运行时以 interactive 模式 patch `SKILL.md`
- **THEN** mode patch MUST 说明自主执行、最多一问、final/pending 二选一
- **AND** mode patch MUST NOT 重复 `message`、`ui_hints`、`options` 或 `files` 的字段级定义
