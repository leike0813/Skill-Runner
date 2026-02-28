## MODIFIED Requirements

### Requirement: Auth management APIs MUST stay externally compatible
phase2 模块化期间，`/v1` 与 `/ui` 鉴权接口的路径与请求语义 MUST 保持兼容。

#### Scenario: existing auth session APIs
- **WHEN** 客户端调用现有 auth start/status/input/cancel/callback 端点
- **THEN** 端点路径与请求字段不变
- **AND** 语义兼容（同样组合返回成功/失败）

### Requirement: Callback completion remains channel-based while runtime is decoupled
callback 仍按 channel + state 消费，但 channel 路由后的业务处理 MUST 由 engine handler 完成。

#### Scenario: callback endpoint hits manager
- **WHEN** callback 端点命中 manager
- **THEN** manager 只做会话定位与状态消费
- **AND** token exchange 与引擎凭据写盘在 engine handler 内完成
