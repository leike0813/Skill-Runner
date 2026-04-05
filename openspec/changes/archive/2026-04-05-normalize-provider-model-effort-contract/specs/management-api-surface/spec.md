## MODIFIED Requirements

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容

系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时保持 `models[].id` 的既有语义与兼容性。

#### Scenario: model list always returns normalized provider_id model supported_effort
- **WHEN** 客户端请求 `GET /v1/engines/{engine}/models`
- **THEN** 每个模型项 MUST 返回 `provider_id`、`model` 与 `supported_effort`
- **AND** `supported_effort` MUST 可被前端直接消费

#### Scenario: single-provider engines expose canonical provider ids
- **WHEN** 客户端请求 `codex`、`gemini` 或 `iflow` 的模型列表
- **THEN** 返回项中的 `provider_id` MUST 分别固定为 `openai`、`google`、`iflowcn`

#### Scenario: unsupported effort models return default-only supported_effort
- **WHEN** 某模型不支持 effort 选择
- **THEN** 接口 MUST 返回 `supported_effort=["default"]`
- **AND** 客户端 MUST NOT 需要再把 `null` 解释为“也许可传 effort”

#### Scenario: opencode runtime probe derives effort variants from verbose json
- **WHEN** `opencode` 通过 runtime probe 刷新模型目录
- **THEN** 系统 MUST 使用 `opencode models --verbose`
- **AND** MUST 从模型对象 `variants` 的键名生成 `supported_effort`
