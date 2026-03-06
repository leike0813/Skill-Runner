## ADDED Requirements

### Requirement: 管理观测接口 MUST 支持 Run Scope 时间线聚合
管理侧接口 MUST 提供基于 run 范围的统一时序聚合数据，用于跨 Orchestrator、RASP、FCMP、Chat、Client 的单时间线渲染。

#### Scenario: 默认返回最近窗口
- **WHEN** 客户端请求 timeline history 且未提供 cursor
- **THEN** 系统返回最近窗口事件（默认 100 条）
- **AND** 返回 cursor floor/ceiling 用于后续增量拉取

#### Scenario: cursor 增量拉取
- **WHEN** 客户端提供 cursor
- **THEN** 系统仅返回 timeline_seq 大于该 cursor 的事件
- **AND** 事件顺序稳定并可连续消费
