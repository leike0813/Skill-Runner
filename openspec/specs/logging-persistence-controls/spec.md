# logging-persistence-controls Specification

## Purpose
定义全局应用日志的持久化、轮换、目录配额，以及 UI 可写日志设置与只读运行时输入的边界。
## Requirements
### Requirement: Global app logs MUST persist to disk with configurable path and policy
The system MUST persist application logs to a disk file under a configurable directory and filename policy.

#### Scenario: Startup initializes global logging
- **WHEN** the service starts and calls `setup_logging()`
- **THEN** logs are emitted to both stream and file handlers
- **AND** file path resolution follows configured logging directory and basename inputs

### Requirement: Global app logs MUST rotate daily with retention controls
The system MUST rotate global log files on a daily schedule and retain files according to configured retention days.

#### Scenario: Daily rollover boundary is reached
- **WHEN** log writes cross the daily rollover boundary
- **THEN** the active log file is rotated by timed policy
- **AND** the number of retained rotated files respects retention configuration

### Requirement: Global app logs directory MUST enforce total quota with oldest-first eviction
The system MUST enforce a max-bytes quota for the global log directory and MUST evict oldest archived logs first when over limit.

#### Scenario: Log directory exceeds quota
- **WHEN** total bytes of active plus archived files for the global app log exceed configured quota
- **THEN** oldest archived files are removed first until under quota or no archive remains
- **AND** the active log file is never deleted by quota cleanup

### Requirement: Logging output MUST support text default and optional JSON format
The system MUST provide text format by default and optional JSON format via configuration.

#### Scenario: JSON format is enabled
- **WHEN** logging format configuration is set to `json`
- **THEN** each emitted record contains at least `timestamp`, `level`, `logger`, and `message` fields
- **AND** logging behavior remains backward compatible in text mode by default

### Requirement: UI 可写日志设置 MUST 由持久化 system settings 承载
系统 MUST 将可由管理 UI 修改的日志设置持久化到 system settings 文件中。

#### Scenario: 首次初始化 settings 文件
- **WHEN** 服务读取日志可写设置且 `data/system_settings.json` 不存在
- **THEN** 系统从 bootstrap 配置文件生成该 settings 文件

#### Scenario: 更新 UI 可写日志设置
- **WHEN** 客户端更新日志可写设置
- **THEN** 系统将 `level`、`format`、`retention_days`、`dir_max_bytes` 写入 `data/system_settings.json`

### Requirement: 非 UI 日志设置 MUST 保持原有配置入口
系统 MUST 保持不可由 UI 修改的日志设置继续走既有配置入口和环境变量覆盖。

#### Scenario: 解析只读日志输入
- **WHEN** 系统构建最终日志配置
- **THEN** `dir`、`file_basename`、`rotation_when`、`rotation_interval` 继续从既有配置入口解析
- **AND** 这些字段不写入 `data/system_settings.json`

### Requirement: 日志系统 MUST 支持设置变更后的热重载
系统 MUST 在日志设置更新后重建 handlers 并应用新的有效配置。

#### Scenario: 提交新的日志设置
- **WHEN** 客户端成功更新日志设置
- **THEN** 系统热重载 logging 配置
- **AND** 不因重复应用导致 handler 重复累积

#### Scenario: 文件 handler 初始化失败
- **WHEN** 系统在热重载中无法初始化文件 handler
- **THEN** 系统退化为 stream-only
- **AND** 保留可观测告警日志

### Requirement: Logging setup MUST degrade safely on file sink failures
The system MUST continue serving with stream logging if file handler initialization fails.

#### Scenario: Log file handler cannot be initialized
- **WHEN** the file sink raises an OS/file-system error during setup
- **THEN** stream logging remains active
- **AND** a warning is emitted with diagnostic fields including `component`, `action`, `error_type`, and `fallback`

### Requirement: CI/tests MUST guard against regressions in logging behavior
The system MUST include tests that verify setup idempotency, format switch behavior, and quota cleanup semantics.

#### Scenario: Logging behavior regression introduced
- **WHEN** tests execute logging unit suites
- **THEN** regressions in handler duplication, JSON payload shape, or quota cleanup are detected and fail CI

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

### Requirement: 日志查询 MUST 限制为白名单日志源
系统日志查询实现 MUST 仅允许读取受控日志源（system/bootstrap），禁止任意文件路径输入，以防止路径穿越与越权读取。

#### Scenario: reject unsupported source
- **WHEN** 客户端请求 `/v1/management/system/logs/query?source=unknown`
- **THEN** 服务返回 `400`
- **AND** 错误提示仅允许 `system|bootstrap`

#### Scenario: source file family is restricted
- **WHEN** 客户端请求 `source=system`
- **THEN** 查询实现仅扫描 `skill_runner.log*`
- **AND** 不会扫描其他非白名单文件

