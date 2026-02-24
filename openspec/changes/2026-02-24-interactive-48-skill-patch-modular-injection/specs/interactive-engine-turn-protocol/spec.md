## MODIFIED Requirements

### Requirement: 运行时 skill patch 注入 MUST 模块化并按固定顺序执行
系统 MUST 将运行时注入划分为固定模块并按确定顺序注入。

#### Scenario: 固定顺序
- **WHEN** patch `SKILL.md`
- **THEN** 注入顺序为：
  1) runtime enforcement
  2) artifact redirection（若有）
  3) output format contract
  4) output schema specification（若可用）
  5) mode patch（auto 或 interactive）

### Requirement: interactive/auto mode 注入 MUST 互斥
系统 MUST 对同一次 patch 仅注入一个 mode 模块。

#### Scenario: interactive
- **WHEN** execution_mode=interactive
- **THEN** 注入 interactive mode 模板
- **AND** 不注入 auto mode 模板

#### Scenario: auto
- **WHEN** execution_mode=auto
- **THEN** 注入 auto mode 模板
- **AND** 不注入 interactive mode 模板
