## MODIFIED Requirements

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容

系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时仅枚举 active engines。

#### Scenario: model and management lists exclude deprecated Gemini
- **WHEN** 客户端请求 engine 列表、模型列表、engine 状态或 UI engine selector
- **THEN** 响应 MUST include active engines only
- **AND** `gemini` MUST NOT appear as a selectable or upgradeable engine
