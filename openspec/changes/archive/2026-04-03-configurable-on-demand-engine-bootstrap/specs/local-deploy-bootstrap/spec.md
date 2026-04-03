## MODIFIED Requirements
### Requirement: 系统 MUST 提供插件友好的运行控制命令
系统 MUST 提供稳定控制命令供插件调用，并覆盖 install/up/down/status/doctor。

#### Scenario: bootstrap/install default to managed subset
- **WHEN** 客户端调用 `skill-runnerctl bootstrap --json` 或 `skill-runnerctl install --json` 且未显式传入 `--engines`
- **THEN** 系统默认仅对 `opencode,codex` 执行 ensure
- **AND** 不再默认对全部受管 engine 做安装

#### Scenario: bootstrap/install supports explicit engine subset
- **WHEN** 客户端调用 `skill-runnerctl bootstrap --engines <csv|all|none> --json`
- **THEN** 系统按该目标集合执行 ensure
- **AND** `all` 保持全量 ensure
- **AND** `none` 仅执行布局初始化、状态刷新与报告落盘

### Requirement: 系统 MUST 提供 bootstrap 控制命令并与 ensure 语义一致
系统 MUST 提供 `skill-runnerctl bootstrap`，并复用 `agent_manager --ensure` 的容错语义：单引擎安装失败可记为 `partial_failure`，但不阻断后续启动链路。

#### Scenario: bootstrap diagnostics record requested and skipped engines
- **WHEN** 用户执行 `skill-runnerctl bootstrap --json`
- **THEN** 诊断报告包含 `summary.requested_engines`
- **AND** 包含 `summary.skipped_engines`
- **AND** 包含 `summary.resolved_mode`

### Requirement: release 安装器 MUST 自动执行 bootstrap 且失败仅告警
系统 MUST 在 release 安装器解压后自动执行一次 bootstrap；bootstrap 非零返回 MUST 仅告警，不阻断安装完成态。

#### Scenario: installer bootstrap defaults to opencode and codex
- **WHEN** 安装器自动执行 bootstrap 且未显式覆盖 engine 集合
- **THEN** 默认仅 ensure `opencode,codex`
- **AND** 其余 engine 保持未安装态直到后续显式 bootstrap/install
