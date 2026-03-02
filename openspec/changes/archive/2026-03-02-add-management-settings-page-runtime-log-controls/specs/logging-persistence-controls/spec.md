# logging-persistence-controls Specification

## ADDED Requirements

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
