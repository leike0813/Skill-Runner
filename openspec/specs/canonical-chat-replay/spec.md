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

### Requirement: chat replay publication MUST be FCMP-derived and MUST NOT shortcut parser semantics

canonical chat replay MUST 只消费已提交的 FCMP 行；parser emission、engine parser helper、
或 live semantic 快捷路径 MUST NOT 直接写入 chat。

#### Scenario: assistant chat row is published from committed FCMP row

- **GIVEN** runtime 即将发布一条 assistant 相关 chat replay
- **WHEN** chat replay publisher 被调用
- **THEN** 输入 MUST 是已经通过 schema 校验并写入 live FCMP journal 的 FCMP row
- **AND** 该 row MUST 已经拥有稳定的 `seq`

#### Scenario: parser emission cannot bypass the runtime event lane

- **GIVEN** parser 识别出 assistant message 或 completion 语义
- **WHEN** 系统将其对外暴露为 chat
- **THEN** 该语义 MUST 先被发布为 runtime event / FCMP event
- **AND** chat replay MUST NOT 从 parser emission 直接生成条目

### Requirement: Canonical chat replay MUST consume backend-projected assistant final display text
Chat replay MUST treat `assistant.message.final` as an already-projected display event and MUST prefer `data.display_text` over raw `data.text` when present.

#### Scenario: assistant final contains projected display text
- **WHEN** an `assistant.message.final` FCMP event includes `data.display_text`
- **THEN** canonical chat replay MUST derive the assistant bubble from `data.display_text`
- **AND** the raw compatibility field `data.text` MUST remain available without becoming the primary chat text

#### Scenario: assistant final has no projected display text
- **WHEN** an `assistant.message.final` FCMP event omits `data.display_text`
- **THEN** canonical chat replay MAY fall back to `data.text`

### Requirement: Chat replay MUST stay free of local structured-output dispatch
Frontend-facing chat replay MUST remain a derived view and MUST NOT require clients to parse `__SKILL_DONE__`, `message`, or `ui_hints` out of assistant final text.

#### Scenario: structured output reaches chat
- **WHEN** a frontend consumes `/chat` or `/chat/history`
- **THEN** the chat payload MUST already reflect the backend-projected display text
- **AND** frontend chat consumers MUST be able to render the message without local structured-output branching

### Requirement: Chat replay inspection MUST stay anchored to chat-replay envelopes
Frontend chat inspection features MUST inspect the `chat-replay` event envelopes already derived by the backend instead of reconstructing alternate event views.

#### Scenario: frontend opens a chat event inspector
- **WHEN** a frontend offers raw-event inspection for a chat bubble
- **THEN** the inspected payload MUST be the original `chat-replay` event envelope consumed by that view
- **AND** the frontend MUST NOT fetch or synthesize a different event source just to populate the inspector

