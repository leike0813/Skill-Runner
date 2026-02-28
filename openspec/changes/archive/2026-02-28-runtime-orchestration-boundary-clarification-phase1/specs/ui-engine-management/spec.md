## ADDED Requirements

### Requirement: UI behavior MUST remain stable under runtime port injection
即使 runtime observability/protocol 改为 ports 注入，管理 UI 的实时与历史读取行为 MUST 保持兼容。

#### Scenario: UI event/log flows after refactor
- **WHEN** 用户在 `/ui/engines`、`/ui/runs` 等页面查看实时与历史数据
- **THEN** 事件流、日志读取与状态展示语义不回归
- **AND** 内部注入失败应返回可诊断错误而非静默异常
