# runtime-event-command-schema Specification

## Purpose
定义运行时核心事件/命令的 JSON Schema 合同与校验策略。
## Requirements
### Requirement: 系统 MUST 维护单一协议 Schema SSOT
系统 MUST 维护覆盖 FCMP/RASP/orchestrator/pending/history/resume-command 的统一 schema 文档。

#### Scenario: 单一真源
- **WHEN** 审查协议对象定义
- **THEN** 存在单一 schema 文件作为 SSOT

### Requirement: 写入路径 MUST 严格校验
系统 MUST 在协议对象落盘/输出前执行 schema 校验，并确保 auth orchestrator event 的 canonical 写入路径被 schema 完整覆盖。

#### Scenario: 不合法事件写入
- **WHEN** 协议对象不满足 schema
- **THEN** 写入被拒绝并返回 `PROTOCOL_SCHEMA_VIOLATION`

#### Scenario: auth orchestrator event canonical payload 通过校验
- **WHEN** orchestration 写入 `auth.session.created`、`auth.method.selected`、`auth.session.busy`、`auth.input.accepted`、`auth.session.completed`、`auth.session.failed` 或 `auth.session.timed_out`
- **THEN** schema MUST 接受这些 canonical payload
- **AND** 系统 MUST NOT 因 schema 漂移把合法 auth submit/complete/fail 路径升级成 `500`

#### Scenario: auth.input.accepted 接受 canonical timestamp 字段
- **WHEN** orchestration 为 callback/code 提交写入 `auth.input.accepted`
- **THEN** 其 `data` MAY 包含 canonical `accepted_at`
- **AND** schema MUST 明确允许该字段
- **AND** 仍 MUST 拒绝未声明的额外字段

### Requirement: 读取路径 MUST 兼容历史脏数据
系统 MUST 在读取历史对象时过滤不合规行，不中断整体读取。

#### Scenario: history 存在脏数据
- **WHEN** 历史文件中有不合规协议对象
- **THEN** 系统跳过不合规行并返回其余合法行

### Requirement: 内部桥接失败 MUST 记录诊断并降级
系统 MUST 在内部桥接对象校验失败时记录 `SCHEMA_INTERNAL_INVALID` 并使用最小安全回退。

#### Scenario: pending 结构异常
- **WHEN** 内部生成的 pending payload 不合法
- **THEN** 系统记录诊断 warning
- **AND** 回退到最小可用 pending 继续执行

### Requirement: Schema 合法性 MUST 接受语义不变量测试约束
系统 MUST 将“schema 合法”与“语义合法”分层校验，并由不变量测试覆盖语义层。

#### Scenario: schema 通过但映射漂移
- **WHEN** 事件 payload 满足 schema
- **AND** FCMP 状态映射不满足不变量合同
- **THEN** 属性/模型测试失败

### Requirement: runtime protocol payloads MUST expose resume ownership metadata
The runtime protocol schema MUST support resume ownership metadata without breaking backward compatibility.

#### Scenario: resume-related FCMP or orchestrator payload is emitted
- **GIVEN** the system emits resume-related FCMP or orchestrator payloads
- **WHEN** the payload is validated against the runtime schema
- **THEN** it MUST support `resume_cause`, `pending_owner`, `source_attempt`, `target_attempt`, `resume_ticket_id`, and `ticket_consumed`
- **AND** these fields MUST remain optional for backward compatibility

### Requirement: pending and history payloads MUST preserve attempt attribution
Pending and history payloads MUST carry attempt attribution in schema-supported fields.

#### Scenario: pending interaction or interaction history row is written
- **GIVEN** the system writes pending interaction or interaction history payloads
- **WHEN** the payload is validated
- **THEN** the schema MUST support `source_attempt`
- **AND** read paths MUST continue to tolerate legacy rows that predate this field

### Requirement: protocol and read-model schemas MUST not encode conversation capability by state name
Schema contracts MUST let clients read effective runtime behavior without inferring it from `waiting_auth`.

#### Scenario: client inspects waiting-state payloads
- **GIVEN** the backend emits waiting-state protocol payloads or status/read-model responses
- **WHEN** the client needs to decide whether a run is session-capable
- **THEN** the contract MUST expose explicit conversation capability fields on read-model/status surfaces
- **AND** `waiting_auth` MUST NOT imply `interactive`

### Requirement: auth payload MUST expose phase and timeout metadata

Auth-related payload 在会话人工 OAuth 返回内容场景下 MUST 使用 `auth_code_or_url` 作为规范值。

#### Scenario: pending auth and auth.input.accepted use auth_code_or_url

- **WHEN** runtime schema 校验 `PendingAuth` 或 `auth.input.accepted`
- **THEN** schema MUST 接受 `auth_code_or_url`
- **AND** MUST NOT 继续要求 `authorization_code`

### Requirement: pending auth payload MUST support callback URL input kind
Pending auth challenge payload MUST support callback URL input kind.

#### Scenario: backend emits pending auth challenge
- **GIVEN** the system emits pending auth challenge payload
- **WHEN** challenge kind or input kind is validated
- **THEN** it MUST support `callback_url`

### Requirement: runtime schema MUST accept custom_provider auth enums
The runtime schema MUST accept `custom_provider` as a legal provider-config waiting_auth value.

#### Scenario: pending auth validates custom_provider
- **WHEN** the backend validates a provider-config `PendingAuth` payload
- **THEN** `auth_method` MUST accept `custom_provider`
- **AND** `challenge_kind` MUST accept `custom_provider`
- **AND** `input_kind` MUST accept `custom_provider`

#### Scenario: method selection and auth input accepted validate custom_provider
- **WHEN** the backend validates `pending_auth_method_selection.available_methods` or `auth.input.accepted.submission_kind`
- **THEN** the schema MUST accept `custom_provider`

### Requirement: orchestrator schema MUST 识别 interaction.reply.accepted
runtime protocol schema MUST 将 `interaction.reply.accepted` 视为一等 orchestrator event，并校验其稳定的 reply-acceptance 元数据。

#### Scenario: reply-accepted orchestrator event 校验成功
- **WHEN** 后端输出一条类型为 `interaction.reply.accepted` 的 orchestrator event
- **THEN** schema 校验 MUST 接受包含 `interaction_id`、`accepted_at` 和 `response_preview` 的 payload
- **AND** 下游协议翻译 MAY 依赖这些字段，而无需绕过 schema 校验

### Requirement: RASP auth diagnostics MUST include structured auth_signal payload
`diagnostic.warning` events for auth-signal matches MUST carry a structured `data.auth_signal` object.

#### Scenario: high-confidence auth signal diagnostic payload
- **GIVEN** backend records a high-confidence auth signal
- **WHEN** writing RASP `diagnostic.warning`
- **THEN** `data.code` MUST be `AUTH_SIGNAL_MATCHED_HIGH`
- **AND** `data.auth_signal.confidence` MUST be `high`
- **AND** `data.auth_signal.matched_pattern_id` MUST be present.

#### Scenario: low-confidence auth signal diagnostic payload
- **GIVEN** backend records a low-confidence auth signal
- **WHEN** writing RASP `diagnostic.warning`
- **THEN** `data.code` MUST be `AUTH_SIGNAL_MATCHED_LOW`
- **AND** `data.auth_signal.confidence` MUST be `low`.

### Requirement: runtime schema MUST accept intermediate agent message events
runtime protocol schema MUST 为非终态 agent 文本提供独立事件合同，并同时支持 FCMP 与 RASP 命名空间中的中间消息事件。

#### Scenario: FCMP intermediate message payload validates
- **WHEN** schema 校验类型为 `assistant.message.intermediate` 的 FCMP 事件
- **THEN** 事件 MUST 通过校验
- **AND** payload MUST 支持 `message_id`、`attempt`、`raw_ref` 等现有消息关联字段

#### Scenario: RASP intermediate message payload validates
- **WHEN** schema 校验类型为 `agent.message.intermediate` 的 RASP 事件
- **THEN** 事件 MUST 通过校验
- **AND** 该合同 MUST 与 `agent.reasoning` / `agent.tool_call` / `agent.command_execution` 并存

