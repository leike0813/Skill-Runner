## ADDED Requirements

### Requirement: naming boundary MUST remain RASP=agent and FCMP=assistant
The runtime MUST keep naming boundary as `agent.*` in RASP and `assistant.*` in FCMP.

#### Scenario: mapping process events across streams
- **GIVEN** RASP 发布 `agent.*` 过程事件
- **WHEN** FCMP 执行映射
- **THEN** FCMP MUST 发布对应 `assistant.*` 事件
- **AND** chat replay role MUST remain `assistant`

### Requirement: final requires prior promoted or direct turn-end promotion path
The runtime SHALL guarantee that final messages are promotion-traceable in publish order.

#### Scenario: final with promoted marker
- **GIVEN** 系统为 `message_id=X` 发布 final
- **WHEN** 该 final 来源于可提升消息池
- **THEN** 系统 MUST 发布 `assistant.message.promoted(message_id=X)`（同 attempt，且先于 final）
