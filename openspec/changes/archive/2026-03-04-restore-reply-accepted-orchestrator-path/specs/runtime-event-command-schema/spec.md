## ADDED Requirements

### Requirement: orchestrator schema MUST 识别 interaction.reply.accepted
runtime protocol schema MUST 将 `interaction.reply.accepted` 视为一等 orchestrator event，并校验其稳定的 reply-acceptance 元数据。

#### Scenario: reply-accepted orchestrator event 校验成功
- **WHEN** 后端输出一条类型为 `interaction.reply.accepted` 的 orchestrator event
- **THEN** schema 校验 MUST 接受包含 `interaction_id`、`accepted_at` 和 `response_preview` 的 payload
- **AND** 下游协议翻译 MAY 依赖这些字段，而无需绕过 schema 校验
