## ADDED Requirements

### Requirement: interactive reply acceptance MUST 先经过 orchestrator event 再进入 FCMP
系统 MUST 让 interactive reply acceptance 先经过 orchestrator event 管线，再进入 FCMP 发布和下游 chat replay 派生。

#### Scenario: reply submit 先写 orchestrator event 再做 FCMP translation
- **WHEN** 一条 waiting interaction 的 reply 提交成功
- **THEN** orchestration 层 MUST 先追加 `interaction.reply.accepted` orchestrator event
- **AND** 下游 FCMP 发布 MUST 从该 orchestrator event 派生
- **AND** 系统 MUST NOT 直接在 reply endpoint 中发布 FCMP 绕过 orchestrator event path
