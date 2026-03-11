## MODIFIED Requirements

### Requirement: Run bundle candidate filtering MUST be rule-file driven
系统 MUST 继续分别构建普通 bundle 与 debug bundle，但该差异 MUST 由 bundle 构建入口决定，而不是由 runtime options 中的 debug 开关驱动。

#### Scenario: debug bundle is an explicit build target
- **WHEN** orchestration 构建 debug bundle
- **THEN** 系统使用 debug bundle 过滤规则
- **AND** 该行为由显式 debug bundle 构建入口触发
- **AND** MUST NOT 依赖 `runtime_options.debug`
