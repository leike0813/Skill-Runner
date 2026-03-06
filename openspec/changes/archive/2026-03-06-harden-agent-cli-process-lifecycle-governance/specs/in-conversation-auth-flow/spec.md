## ADDED Requirements

### Requirement: 会话鉴权 CLI 进程 MUST 纳入统一 lease 治理
会话鉴权在使用 CLI delegate 路径时，MUST 为进程登记 lease；会话终态或取消时 MUST 关闭 lease，并使用统一终止器。

#### Scenario: 取消鉴权会话
- **WHEN** 用户取消活跃鉴权会话
- **THEN** 系统终止受管鉴权进程
- **AND** 对应 lease 被关闭
