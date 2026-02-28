## ADDED Requirements

### Requirement: API surface MUST remain compatible during services/runtime reorganization
在本次目录重构中，对外 `/v1` 管理与运行接口路径、请求语义、关键响应字段 MUST 保持兼容。

#### Scenario: Existing API clients
- **WHEN** 现有客户端调用 `/v1` 端点
- **THEN** 不因内部模块迁移出现破坏性行为变化
- **AND** 请求/响应主字段语义保持一致
