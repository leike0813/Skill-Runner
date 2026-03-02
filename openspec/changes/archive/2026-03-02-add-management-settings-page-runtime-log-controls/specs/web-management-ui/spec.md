# web-management-ui Specification

## MODIFIED Requirements

### Requirement: 系统 MUST 提供 `/ui` 管理界面用于技能可视化管理
系统 MUST 暴露 `/ui` 页面，用户可在页面中查看当前已安装技能列表。

#### Scenario: 打开管理界面
- **WHEN** 用户访问 `/ui`
- **THEN** 系统返回可用页面
- **AND** 页面包含技能列表区域与技能包上传区域
- **AND** data reset 危险区不再直接出现在首页

### Requirement: 管理界面 MUST 提供独立 Settings 页面
系统 MUST 提供 `/ui/settings` 页面，承载运行时设置与高危维护操作。

#### Scenario: 打开 Settings 页面
- **WHEN** 用户访问 `/ui/settings`
- **THEN** 页面展示日志设置区域与 data reset 危险区

### Requirement: 管理界面 MUST 让 data reset 选项反映真实系统能力
系统 MUST 依据当前系统能力显示或隐藏可选清理项，避免暴露未启用能力的伪选项。

#### Scenario: engine auth session 日志持久化关闭
- **WHEN** `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` 为关闭状态
- **THEN** `/ui/settings` 页面完全隐藏 engine auth session 清理选项

### Requirement: 管理界面 MUST 支持最小运行时日志设置管理
系统 MUST 在 Settings 页面提供最小可写日志设置，并展示不可在页面修改的只读运行时输入。

#### Scenario: 查看 Settings 页面日志设置
- **WHEN** 用户访问 `/ui/settings`
- **THEN** 页面展示可写日志设置 `level`、`format`、`retention_days`、`dir_max_bytes`
- **AND** 页面展示只读日志输入 `dir`、`file_basename`、`rotation_when`、`rotation_interval`
