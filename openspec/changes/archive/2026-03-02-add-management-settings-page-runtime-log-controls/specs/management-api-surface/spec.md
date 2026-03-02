# management-api-surface Specification

## MODIFIED Requirements

### Requirement: 系统 MUST 提供统一管理 API 面
系统 MUST 提供前端无关的管理 API，覆盖 Skill 管理、Engine 管理、Run 管理三类资源。

#### Scenario: 管理 API 资源分组
- **WHEN** 客户端查询管理能力
- **THEN** 可在统一命名空间访问 Skill / Engine / Run 管理资源
- **AND** 可通过系统设置接口访问运行时设置与维护操作

### Requirement: 管理 API MUST 提供系统设置读取与更新接口
系统 MUST 提供读取和更新运行时系统设置的管理接口。

#### Scenario: 读取系统设置
- **WHEN** 客户端调用 `GET /v1/management/system/settings`
- **THEN** 响应包含当前有效日志设置
- **AND** 区分可写设置与只读运行时输入

#### Scenario: 更新日志设置
- **WHEN** 客户端调用 `PUT /v1/management/system/settings`
- **AND** 请求仅包含允许写入的日志字段
- **THEN** 系统持久化新的设置值
- **AND** 触发日志配置热重载

#### Scenario: 提交只读字段
- **WHEN** 客户端在更新请求中提交只读日志字段
- **THEN** 系统返回 `400`

### Requirement: 数据重置接口 MUST 保持兼容并反映有效能力
系统 MUST 保持现有数据重置接口的路径与确认语义兼容，并在 feature off 时拒绝实际清理未启用能力的数据。

#### Scenario: feature off 时传入 engine auth session 清理开关
- **WHEN** 客户端调用 `POST /v1/management/system/reset-data`
- **AND** `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` 为关闭状态
- **THEN** 系统将 `include_engine_auth_sessions` 归一化为 `false`
- **AND** 不把 `data/engine_auth_sessions` 纳入目标路径
