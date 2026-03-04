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

