## ADDED Requirements

### Requirement: 系统 MUST 以 Statechart 维护 session 运行时 SSOT
系统 MUST 提供并维护三层状态图（Lifecycle、Turn Decision、Timeout/Recovery）作为唯一状态机参考。

#### Scenario: SSOT 文档可追溯
- **WHEN** 开发者查看 session 状态语义
- **THEN** 可在 `docs/session_runtime_statechart_ssot.md` 获取完整状态图与映射附录

### Requirement: 实现 MUST 使用 canonical 状态机表
关键状态转换 MUST 由实现侧状态机表统一定义。

#### Scenario: 状态机表驱动关键事件
- **WHEN** 编排处理回复、自动决策、重启恢复
- **THEN** 转换事件来自统一 canonical event 集
- **AND** 不依赖散落的 sticky 兼容分支

### Requirement: auto MUST 建模为 interactive 子集
系统 MUST 在同一状态机范式内处理 `auto` 与 `interactive`。

#### Scenario: 终态映射一致
- **WHEN** run 处于 `auto` 或 `interactive`
- **THEN** 终态均映射为 `succeeded|failed|canceled`
