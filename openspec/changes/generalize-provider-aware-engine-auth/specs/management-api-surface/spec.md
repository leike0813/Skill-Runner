## MODIFIED Requirements

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容

系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时保持 `models[].id` 的既有语义与兼容性。

#### Scenario: provider-aware engine model list returns provider_id

- **WHEN** 客户端请求 `GET /v1/engines/{engine}/models`，且 `engine` 为 `opencode` 或 `qwen`
- **THEN** 返回的模型项 MUST 额外包含 `provider`、`provider_id` 与 `model`
- **AND** `id` MUST 继续保持既有兼容语义

#### Scenario: qwen overlapping model ids remain distinguishable

- **WHEN** `qwen` 不同 provider 暴露同名模型
- **THEN** 客户端 MUST 可以通过 `provider_id + model` 区分条目
- **AND** 旧客户端仅读取 `id` 时不应导致路由级 breaking change

### Requirement: Provider-aware engine 鉴权启动 MUST 支持 provider_id

系统 MUST 允许 provider-aware engine 在鉴权 start 请求中显式携带 `provider_id`，并按 capability matrix 校验组合。

#### Scenario: provider-aware auth start uses provider_id

- **WHEN** 客户端调用 `/v1/engines/auth/*/sessions` 为 `opencode` 或 `qwen` 发起鉴权
- **THEN** 请求体中的 `provider_id` MUST 作为标准 provider 选择器参与校验与会话创建

### Requirement: Provider-aware auth import MUST use provider_id-specific rules

系统 MUST 允许 provider-aware engine 的导入规格与导入提交按 `provider_id` 选择实际规则，而不是把导入能力视为 engine 级全局常量。

#### Scenario: qwen oauth import is supported

- **WHEN** 客户端请求 `GET /v1/management/engines/qwen/auth/import/spec?provider_id=qwen-oauth`
- **THEN** 系统返回 `oauth_creds.json` 导入规格

#### Scenario: qwen coding-plan import is hidden

- **WHEN** 客户端请求 `GET /v1/management/engines/qwen/auth/import/spec?provider_id=coding-plan-global`
- **THEN** 系统 MUST 拒绝该导入规格或返回 unsupported
