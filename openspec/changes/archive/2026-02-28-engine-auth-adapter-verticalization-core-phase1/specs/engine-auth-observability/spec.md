## ADDED Requirements

### Requirement: Transport orchestrator MUST 与 engine-specific 逻辑解耦
系统 MUST 保证 transport orchestrator 不包含 engine-specific 业务分支，改为通过 driver capability 与 driver 对象分发。

#### Scenario: oauth_proxy 会话启动
- **WHEN** orchestrator 启动 oauth_proxy 会话
- **THEN** 仅根据 capability/driver 注册结果执行
- **AND** orchestrator 中不出现 `if engine == ...` 分支

#### Scenario: cli_delegate 会话启动
- **WHEN** orchestrator 启动 cli_delegate 会话
- **THEN** method 与输入分发由 capability/driver 决定
- **AND** transport 状态机语义保持不变

### Requirement: 鉴权日志与状态语义 MUST 保持兼容
系统 MUST 在重构后保持现有 transport 日志目录与状态字段语义兼容。

#### Scenario: 兼容快照输出
- **WHEN** 客户端读取 auth session snapshot
- **THEN** 现有关键字段（transport/status/auth_method/provider_id/log_root）语义不回归
