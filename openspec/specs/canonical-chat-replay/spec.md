# canonical-chat-replay Specification

## Purpose
TBD - created by archiving change canonical-chat-replay-ssot. Update Purpose after archive.
## Requirements
### Requirement: Canonical chat replay is the chat SSOT

Canonical chat replay MUST be the only authoritative source for rendering user, assistant, and system chat bubbles.

#### Scenario: Live and history use the same chat source

- **GIVEN** a run is active or recently completed
- **WHEN** the client streams `/chat` or fetches `/chat/history`
- **THEN** both responses reflect the same canonical chat ordering

### Requirement: Frontends must not optimistic-render chat bubbles

Frontends MUST NOT append local chat bubbles for replies or auth submissions before the backend publishes canonical chat replay rows.

#### Scenario: Reply submit waits for backend chat replay

- **GIVEN** a user submits a reply
- **WHEN** the frontend waits for the chat update
- **THEN** the chat bubble only appears after it is received from canonical chat replay

### Requirement: 普通用户回复气泡 MUST 来自 canonical 的 FCMP reply-accepted 事件
canonical chat replay MUST 从 FCMP `interaction.reply.accepted` 事件派生普通用户回复气泡，而该 FCMP 又必须来自 canonical 的后端 reply-acceptance 发布路径。

#### Scenario: chat replay 在无 fallback 的情况下显示普通用户回复
- **WHEN** 一条 interactive 用户回复被成功接受
- **THEN** canonical chat replay MUST 基于 FCMP `interaction.reply.accepted` 产出对应的 `user` 气泡
- **AND** 系统 MUST NOT 通过 interaction history fallback 或 endpoint 本地合成来重建该气泡

### Requirement: chat replay contract MUST include assistant_process kind
chat replay 合同 MUST 同时支持 `assistant_process` 与 `assistant_message` kind，用于分别承载真正的 assistant 过程语义和非终态 agent 文本。

#### Scenario: schema validation accepts assistant process and message kinds
- **GIVEN** chat replay 事件 `role=assistant`
- **WHEN** 执行 schema 校验
- **THEN** `kind=assistant_process` MUST 通过校验
- **AND** `kind=assistant_message` MUST 通过校验

### Requirement: derivation rules MUST map FCMP process events to assistant_process
chat replay 派生规则 MUST 将 FCMP 过程事件映射为 `assistant_process`，并将非终态 agent message 映射为 `assistant_message`。

#### Scenario: derive process and intermediate kinds from FCMP
- **GIVEN** FCMP 事件类型为 `assistant.reasoning`
- **WHEN** 执行 chat replay 派生
- **THEN** 生成事件 MUST 为 `role=assistant` + `kind=assistant_process`

#### Scenario: derive intermediate message from FCMP
- **GIVEN** FCMP 事件类型为 `assistant.message.intermediate`
- **WHEN** 执行 chat replay 派生
- **THEN** 生成事件 MUST 为 `role=assistant` + `kind=assistant_message`

