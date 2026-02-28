## MODIFIED Requirements

### Requirement: Auth session APIs MUST keep external contract stable during runtime modularization
在 auth runtime 模块化过程中，系统 MUST 保持现有 `/v1` 与 `/ui` 鉴权端点及请求语义兼容。

#### Scenario: 既有 start/status/input/cancel 请求可继续工作
- **WHEN** 客户端调用现有鉴权接口
- **THEN** 不应因内部重构产生破坏性变更（路径、必填字段、状态语义保持兼容）

### Requirement: Manager MUST behave as façade
`EngineAuthFlowManager` MUST 作为兼容 façade，而不是 engine-specific 业务承载点。

#### Scenario: start 请求进入 façade 编排链
- **WHEN** 调用 `start_session(...)`
- **THEN** manager 负责锁与编排
- **AND** 具体启动逻辑由 runtime service 承接（`session_start_planner` + `session_starter`）
