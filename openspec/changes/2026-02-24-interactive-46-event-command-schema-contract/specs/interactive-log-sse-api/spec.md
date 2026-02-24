## MODIFIED Requirements

### Requirement: `chat_event` 输出 MUST 满足 FCMP Schema
系统 MUST 在 SSE 输出前对 `chat_event` 做 schema 校验。

#### Scenario: SSE 输出合法性
- **WHEN** 服务端推送 `event=chat_event`
- **THEN** 事件 envelope 与 payload 满足 `fcmp_event_envelope` 合同

### Requirement: FCMP history MUST 过滤不合规历史行
系统 MUST 对历史重放进行兼容过滤，而不是直接失败。

#### Scenario: 历史重放兼容
- **WHEN** 事件历史中包含旧版不合规行
- **THEN** 服务端过滤该行并继续返回合法事件
