## MODIFIED Requirements

### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: run create accepts normalized provider model effort triple
- **WHEN** 客户端调用 `POST /v1/jobs`
- **THEN** 请求体 SHOULD 以 `provider_id + model + effort` 传递模型选择
- **AND** 系统 MUST 将其规范化为稳定的内部三元组

#### Scenario: legacy provider/model@effort remains input-compatible
- **WHEN** 客户端仍以 `model="provider/model@effort"`、`model="provider/model"` 或 `model="model@effort"` 提交
- **THEN** 系统 MUST 继续兼容解析
- **AND** 兼容仅存在于请求解析层，不改变内部与对外返回的规范化字段语义

#### Scenario: multi-provider engines reject missing provider in standard form
- **GIVEN** 引擎为 `claude`、`qwen` 或 `opencode`
- **WHEN** 客户端以标准三元组方式提交但缺失 `provider_id`
- **AND** `model` 字段也不包含旧式 provider 前缀
- **THEN** 系统 MUST 拒绝请求

#### Scenario: single-provider engines ignore provider input
- **GIVEN** 引擎为 `codex`、`gemini` 或 `iflow`
- **WHEN** 客户端提交任意值或空值的 `provider_id`
- **THEN** 系统 MUST 不改变行为
- **AND** 内部 MUST 收口到该引擎的 canonical provider
