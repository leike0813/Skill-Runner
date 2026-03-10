# runtime-event-ordering-contract Specification

## Purpose
TBD - created by archiving change formalize-streamed-rasp-fcmp-ordering-contracts. Update Purpose after archive.
## Requirements
### Requirement: Publish order MUST be the canonical source for active runtime events
系统 MUST 将 active run 中 runtime event 的 publish order 作为 canonical order source。audit mirror、history materialization 与 batch backfill MAY 持久化或补历史，但 MUST NOT 重新定义 active order。

#### Scenario: audit mirror cannot redefine active order
- **WHEN** active run 的 runtime event 已经按 canonical publish order 发布
- **THEN** 后续 audit mirror 写盘顺序 MUST NOT 改变这些事件的 canonical order

### Requirement: Runtime event publication MUST pass through an ordering gate
系统 MUST 通过统一的顺序仲裁层决定候选事件是否可发布，而不是允许各来源直接对外 publish。

#### Scenario: unmet prerequisite causes buffering
- **WHEN** 某个候选事件依赖的前置事件尚未满足
- **THEN** 顺序 gate MUST 先将其缓冲
- **AND** MUST NOT 允许其越过前置事件先发布

### Requirement: FCMP and RASP MUST be separately ordered but explicitly correlated
系统 MUST 允许 FCMP 与 RASP 各自维护独立序号空间，同时 MUST 通过显式关联字段建立稳定映射与因果关系。

#### Scenario: dual-stream ordering keeps explicit linkage
- **WHEN** 同一 runtime emission 派生出 FCMP 与 RASP
- **THEN** FCMP 与 RASP MAY 使用不同的 seq 空间
- **AND** MUST 通过 `publish_id` 建立稳定关联

### Requirement: Conversation lifecycle FCMP MUST be normalized to state.changed only
系统 MUST 将 conversation lifecycle FCMP 收敛为 `conversation.state.changed` 单轨模型，并将 terminal 语义折叠进其 `data.terminal`。

#### Scenario: redundant terminal lifecycle events are removed
- **WHEN** run 进入 terminal
- **THEN** 系统 MUST 仅发布 terminal `conversation.state.changed`
- **AND** MUST NOT 再发布 `conversation.completed` 或 `conversation.failed`

### Requirement: Causal publication constraints MUST be explicit for auth, waiting, reply, and terminal flows
系统 MUST 为 auth、waiting、reply、terminal 等关键链路定义可测试的因果发布约束，禁止后继事件在前置事件之前可见。

#### Scenario: dependent auth challenge follows selection guidance
- **WHEN** auth challenge 依赖用户先选择鉴权方式
- **THEN** 选择引导事件 MUST 先发布
- **AND** 依赖该选择结果的 challenge/link MUST 晚于该引导事件

#### Scenario: single-method auth bypasses selection and preserves active challenge
- **WHEN** auth route 只有单一可用方式
- **THEN** 系统 MUST 直接进入 challenge-active
- **AND** MUST NOT 发布 `auth.method.selection.required`
- **AND** 若命中已有 active auth session，系统 MUST 重投影现有 challenge
- **AND** MUST NOT 将 busy 恢复错误降级为 method-selection

#### Scenario: terminal lifecycle follows final semantic prerequisites
- **WHEN** run 要发布 terminal `conversation.state.changed`
- **THEN** 对应最终语义前置条件 MUST 已满足
- **AND** terminal projection MUST NOT 早于这些条件可见

### Requirement: Live SSE and history replay MUST preserve the same canonical order
系统 MUST 保证 live SSE 与 `/events/history` 对同一 run 的返回顺序一致，并且该顺序 MUST 等于 canonical publish order。

#### Scenario: replay path cannot reorder live truth
- **WHEN** 客户端先消费 live SSE，再用 cursor 调用 `/events/history`
- **THEN** history MUST 返回与 live truth 一致的相对顺序
- **AND** memory-first 与 audit-fallback 的差异 MUST NOT 改变顺序

### Requirement: Batch rebuild MUST be parity and backfill only
系统 MAY 保留 batch rebuild 能力用于 parity test、audit fallback 和冷回放，但 MUST NOT 让 batch rebuild 覆盖已发布的 live order。

#### Scenario: batch rebuild is secondary
- **WHEN** active run 已经存在 canonical live-published event order
- **THEN** batch rebuild 只能用于校验或补历史
- **AND** MUST NOT 成为 live delivery 或 active order 的前置

### Requirement: Auth completion ordering MUST depend on canonical completion source only
系统 MUST 仅允许 canonical auth completion source 解锁 `auth.completed` 与 `waiting_auth -> queued`。

#### Scenario: challenge and busy cannot unlock completion
- **WHEN** 系统发布 `auth.challenge.updated`、`auth.session.busy` 或相关 diagnostic event
- **THEN** 这些事件 MUST NOT 解锁 `auth.completed`
- **AND** MUST NOT 解锁 `conversation.state.changed(waiting_auth -> queued)`

### Requirement: Legacy auth_ready semantics MUST be removed from ordering rules
顺序合同 MUST 明确 `auth_ready` 已退役，readiness-like signal 不得参与 completion ordering。

#### Scenario: readiness-like signal is non-authoritative
- **WHEN** 系统观察到凭据可用、CLI 可执行或类似 readiness-like signal
- **THEN** 该信号 MAY 进入 observability
- **AND** MUST NOT 作为 auth completion 排序前置或释放条件

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

