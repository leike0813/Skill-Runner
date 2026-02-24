## MODIFIED Requirements

### Requirement: 观测层 MUST 对协议事件执行写前校验
系统 MUST 在落盘 `events.jsonl` 与 `fcmp_events.jsonl` 前执行 schema 校验。

#### Scenario: FCMP 落盘
- **WHEN** 观测层写入 `fcmp_events.jsonl`
- **THEN** 每条事件必须通过 `fcmp_event_envelope` 校验

### Requirement: 观测层 MUST 兼容旧历史读取
系统 MUST 在 history 读取阶段过滤不合规行。

#### Scenario: 历史存在旧行
- **WHEN** 读取到不符合当前 schema 的历史行
- **THEN** 该行被忽略
- **AND** 其余合法事件正常返回
