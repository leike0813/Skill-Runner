## MODIFIED Requirements

### Requirement: UI shell session launch contract

UI shell 启动链路 MUST 支持可选 `custom_model`，并保持普通启动路径兼容。

#### Scenario: Start UI shell with provider-backed model

- **WHEN** `/ui/engines/tui/session/start` 收到 `engine` 与 `custom_model=provider/model`
- **THEN** 路由 MUST 将该值传递到 UI shell manager
- **AND** manager MUST 校验 `custom_model` 为严格 `provider/model`

#### Scenario: Claude session injects provider-backed model

- **WHEN** `claude` 的 UI shell 会话以 `custom_model=provider/model` 启动
- **THEN** 系统 MUST 复用现有 custom provider 解析逻辑
- **AND** MUST 将 provider 鉴权与模型信息写入 session-local `.claude/settings.json`
