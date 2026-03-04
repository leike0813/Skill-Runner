## ADDED Requirements

### Requirement: 普通用户回复气泡 MUST 来自 canonical 的 FCMP reply-accepted 事件
canonical chat replay MUST 从 FCMP `interaction.reply.accepted` 事件派生普通用户回复气泡，而该 FCMP 又必须来自 canonical 的后端 reply-acceptance 发布路径。

#### Scenario: chat replay 在无 fallback 的情况下显示普通用户回复
- **WHEN** 一条 interactive 用户回复被成功接受
- **THEN** canonical chat replay MUST 基于 FCMP `interaction.reply.accepted` 产出对应的 `user` 气泡
- **AND** 系统 MUST NOT 通过 interaction history fallback 或 endpoint 本地合成来重建该气泡
