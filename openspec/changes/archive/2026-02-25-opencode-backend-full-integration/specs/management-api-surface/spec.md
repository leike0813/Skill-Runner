## ADDED Requirements

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容
系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时保持 `models[].id` 的既有语义与兼容性。

#### Scenario: opencode 模型列表返回 provider/model
- **WHEN** 客户端请求 `GET /v1/engines/opencode/models`
- **THEN** 返回的模型项中 `id` 保持 `provider/model`
- **AND** 每个模型项额外包含 `provider` 与 `model` 字段

#### Scenario: 非 opencode 引擎兼容
- **WHEN** 客户端请求其他引擎模型列表
- **THEN** 原有字段语义保持不变
- **AND** 旧客户端仅读取 `models[].id` 不受影响
