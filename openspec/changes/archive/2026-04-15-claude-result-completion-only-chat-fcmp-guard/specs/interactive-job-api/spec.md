## ADDED Requirements

### Requirement: promoted final messages MUST come from real message candidates

系统 MUST 只基于真实 assistant message candidate 进行 promoted/final 收敛，不得把 Claude
completion summary echo 当成常规候选正文。

#### Scenario: Claude result echo follows a real assistant body message

- **GIVEN** Claude 当前 turn 已经产出真实 assistant body message
- **AND** 同一 turn 的 `type=result.result` 回显了相同或等价文本
- **WHEN** runtime 收敛 promoted/final assistant message
- **THEN** promoted/final MUST 绑定真实 assistant body message 的 `message_id`
- **AND** `type=result.result` MUST NOT 再注册新的常规候选消息
