# management-api-surface Specification

## MODIFIED Requirements

### Requirement: 系统 MUST 提供统一管理 API 面
系统 MUST 提供前端无关的管理 API，覆盖 Skill 管理、Engine 管理、Run 管理三类资源。

#### Scenario: 管理 API 资源分组
- **WHEN** 客户端查询管理能力
- **THEN** 可在统一命名空间访问 Skill / Engine / Run 管理资源
- **AND** engine 管理摘要只暴露稳定缓存化字段

### Requirement: Engine 管理摘要 MUST 不再暴露 auth probe 或 sandbox probe 字段
系统 MUST 将 engine 管理摘要收敛为缓存化版本信息与稳定计数字段，不再暴露误导性的 auth/sandbox 摘要。

#### Scenario: 查询 engine 摘要列表
- **WHEN** 客户端调用 `GET /v1/management/engines`
- **THEN** 响应仅返回缓存化的 `cli_version`
- **AND** 包含 `models_count`
- **AND** 不返回 `auth_ready`
- **AND** 不返回 `sandbox_status`

### Requirement: Engine 管理详情 MUST 不再暴露 auth probe 或 sandbox probe 字段
系统 MUST 在 engine 详情中移除 auth/sandbox 摘要字段，并保持模型详情读取能力。

#### Scenario: 查询单个 engine 详情
- **WHEN** 客户端调用 `GET /v1/management/engines/{engine}`
- **THEN** 响应包含 `engine`、`cli_version`、`models_count`、`models`
- **AND** 不返回 `auth_ready`
- **AND** 不返回 `sandbox_status`
