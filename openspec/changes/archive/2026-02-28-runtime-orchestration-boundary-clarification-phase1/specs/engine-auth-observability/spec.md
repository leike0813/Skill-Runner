## ADDED Requirements

### Requirement: Auth observability integration MUST remain compatible after boundary clarification
边界澄清后，auth 与 run observability 的交互行为 MUST 保持兼容，不得影响会话状态和事件可见性。

#### Scenario: Delegated auth and run observability coexistence
- **WHEN** 启动鉴权会话并并发读取 run 观测信息
- **THEN** auth 生命周期与 run 事件流各自正常推进
- **AND** 端口注入改造不改变既有状态机语义
