# ui-engine-inline-terminal Specification

## MODIFIED Requirements

### Requirement: 系统 MUST 对内嵌终端启用 fail-closed 沙箱策略
系统 MUST 在启动引擎 TUI 前完成 sandbox 可用性探测并暴露结果；探测结果默认用于可观测，不作为阻断启动的硬门槛。

#### Scenario: sandbox 仅在终端 banner 中展示
- **WHEN** 用户启动或查看内嵌终端会话
- **THEN** sandbox 信息在 terminal/banner 区域展示
- **AND** 不再在 engine 管理列表摘要中复用该状态
