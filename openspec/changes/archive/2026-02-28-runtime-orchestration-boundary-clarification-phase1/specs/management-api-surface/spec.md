## ADDED Requirements

### Requirement: Runtime/orchestration boundary refactor MUST preserve external API semantics
本次边界澄清属于内部重构，对外 `/v1` 与 `/ui` 接口语义 MUST 保持兼容。

#### Scenario: Existing API clients after boundary refactor
- **WHEN** 现有客户端调用已存在的管理、作业与观测接口
- **THEN** 路由路径、输入/输出主字段与状态语义保持不变
- **AND** 不因内部端口注入改造产生破坏性差异
