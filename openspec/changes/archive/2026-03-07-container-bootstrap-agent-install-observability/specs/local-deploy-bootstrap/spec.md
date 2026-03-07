## ADDED Requirements

### Requirement: Container bootstrap MUST expose actionable agent installation diagnostics
系统 MUST 在容器启动期间输出可操作的 agent 安装诊断信息，至少包含引擎名、返回码、耗时与失败摘要。

#### Scenario: Engine install failure emits structured diagnostics
- **WHEN** `agent_manager --ensure` 对某个 engine 安装失败
- **THEN** 启动日志包含该 engine 的结构化失败信息
- **AND** 信息包含 `engine`, `exit_code`, `duration_ms`, `stderr_summary`

### Requirement: Bootstrap diagnostics MUST be persisted under data dir
系统 MUST 将启动阶段诊断持久化到数据目录，便于离线排障。

#### Scenario: Bootstrap report is generated
- **WHEN** 容器完成启动流程
- **THEN** `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json` 存在
- **AND** 报告包含每个 engine 的 ensure/install 结果
