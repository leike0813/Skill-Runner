## ADDED Requirements

### Requirement: Bootstrap diagnostics log MUST be persisted with rotation
系统 MUST 持久化启动阶段诊断日志，并通过轮转限制日志文件增长。

#### Scenario: Bootstrap log file exists after startup
- **WHEN** 容器完成启动
- **THEN** `${SKILL_RUNNER_DATA_DIR}/logs/bootstrap.log` 存在
- **AND** 启动阶段关键事件可在该日志中检索到

#### Scenario: Large bootstrap logs are rotated
- **WHEN** 启动阶段日志超过配置阈值
- **THEN** 系统按轮转策略生成分片文件
- **AND** 不影响主服务继续启动
