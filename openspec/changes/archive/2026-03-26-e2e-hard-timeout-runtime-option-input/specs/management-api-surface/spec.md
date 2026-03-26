## ADDED Requirements

### Requirement: Management API MUST expose service runtime option defaults for client-side form defaults

系统 MUST 提供 management API，让前端读取服务级 runtime option 默认值，用于动态表单预填。

#### Scenario: read service runtime defaults
- **WHEN** 客户端调用 `GET /v1/management/runtime-options`
- **THEN** 响应包含 `service_defaults`
- **AND** `service_defaults.hard_timeout_seconds` 等于当前服务配置的 `ENGINE_HARD_TIMEOUT_SECONDS`

### Requirement: Management skill detail MUST expose runtime default options

系统 MUST 在 skill detail 响应中暴露 skill manifest 的 runtime 默认选项，以支持前端构建带默认值的执行表单。

#### Scenario: skill detail includes runtime default options
- **WHEN** 客户端调用 `GET /v1/management/skills/{skill_id}`
- **AND** 该 skill manifest 声明了 `runtime.default_options`
- **THEN** 响应包含 `runtime.default_options`
- **AND** 客户端无需再读取原始 runner 文件即可获取 skill 默认 runtime option
