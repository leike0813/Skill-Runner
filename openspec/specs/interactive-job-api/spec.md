# interactive-job-api Specification

## Purpose
定义任务执行模式选择、待决交互查询和交互回复提交的 API 约束。
## Requirements
### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: 未显式提供执行模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且未提供 `execution_mode`
- **THEN** 系统按 `auto` 模式执行
- **AND** 现有接口行为不变

#### Scenario: 显式请求 interactive 模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且 `execution_mode=interactive`
- **THEN** 系统接受请求并按交互模式编排

### Requirement: 系统 MUST 提供待决交互查询接口
The pending payload minimum viability MUST be guaranteed by backend-owned generation and MUST NOT depend on agent-structured ask_user output.

#### Scenario: waiting_user 下总能返回可回复 pending
- **GIVEN** run 状态为 `waiting_user`
- **WHEN** 客户端调用 pending 接口
- **THEN** 返回可用于 reply 的 `interaction_id` 与 `prompt`
- **AND** 其来源可以是后端基线生成，而非 ask_user 原样透传

### Requirement: 系统 MUST 提供交互回复接口
The reply protocol MUST remain `interaction_id + response` driven and MUST NOT introduce semantic coupling to `kind`.

#### Scenario: kind 仅兼容展示
- **WHEN** pending 载荷包含 `kind`
- **THEN** 客户端可用于展示
- **AND** 后端不依赖该字段做语义理解或强约束验证

### Requirement: 系统 MUST 校验请求执行模式是否被 Skill 允许
系统 MUST 在 run 创建阶段校验 `execution_mode` 是否属于 Skill 声明的 `execution_modes`。

#### Scenario: 请求模式被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求模式不被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 不包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_EXECUTION_MODE_UNSUPPORTED`

### Requirement: 系统 MUST 支持 interactive 严格回复开关
系统 MUST 提供 `interactive_require_user_reply` 开关控制交互回合是否必须等待用户回复。

#### Scenario: 未显式提供开关
- **WHEN** 客户端创建 interactive run 且未提供开关
- **THEN** 系统使用默认值 `interactive_require_user_reply=true`

#### Scenario: 显式关闭严格回复
- **WHEN** 客户端创建 interactive run 且 `interactive_require_user_reply=false`
- **THEN** 系统接受并按“允许超时自动决策”语义执行

### Requirement: reply 接口 MUST 支持自由文本回复
系统 MUST 允许客户端提交自由文本作为用户答复，不要求固定 JSON 回复结构。

#### Scenario: 提交自由文本回复
- **WHEN** 客户端调用 reply 接口提交文本答复
- **THEN** 系统接受该答复
- **AND** 不要求按 `kind` 提供固定字段对象

### Requirement: 系统 MUST 记录交互回复来源
系统 MUST 区分并持久化“用户回复”和“系统自动决策回复”。

#### Scenario: 用户主动回复
- **WHEN** 客户端调用 reply 接口提交合法回复
- **THEN** 交互历史记录 `resolution_mode=user_reply`

#### Scenario: 超时自动决策
- **WHEN** strict=false 且等待超过超时阈值
- **THEN** 系统生成自动回复并记录 `resolution_mode=auto_decide_timeout`

### Requirement: 系统 MUST 校验请求引擎是否被 Skill 允许
系统 MUST 在 run 创建阶段基于 Skill 的 `effective_engines` 校验请求引擎是否允许执行。

#### Scenario: 请求引擎在有效集合内
- **GIVEN** Skill 的 `effective_engines` 包含请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求命中显式不支持引擎
- **GIVEN** Skill 在 `runner.json.unsupported_engines` 中声明了请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`

#### Scenario: 请求引擎不在允许集合
- **GIVEN** Skill 显式声明 `runner.json.engines` 且请求引擎不在该集合（或被排除后不在 `effective_engines`）
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`

### Requirement: waiting_user 进入条件 MUST 独立于 ask_user 结构体
系统 MUST 允许在缺少或损坏 ask_user 结构时，仍通过 interactive gate 进入等待态。

#### Scenario: 缺失 ask_user 仍可等待用户
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** 当前回合未检测到 done marker
- **THEN** run 可进入 `waiting_user`
- **AND** pending/reply 闭环保持可用

### Requirement: API 状态与诊断 MUST 反映双轨完成与回合上限策略
系统 MUST 向客户端公开稳定、可消费的完成告警与失败原因。

#### Scenario: 软条件完成返回稳定 warning
- **WHEN** interactive 回合未检测到 done marker 但输出通过 schema 校验并完成
- **THEN** API 响应中的诊断/告警包含 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: 超轮次失败返回稳定错误码
- **WHEN** interactive 回合达到 `max_attempt` 且本回合无完成证据
- **THEN** API 返回 `failed`
- **AND** 失败原因包含 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`

### Requirement: 对外交互会话配置 MUST 不暴露 legacy kind 字段
系统 MUST 从对外读取接口中移除 `interactive_profile.kind` 语义。

#### Scenario: result/status 读取不返回 kind
- **WHEN** 客户端读取状态或结果
- **THEN** 响应不包含 `interactive_profile.kind`
- **AND** 保持 `execution_mode`、`pending_interaction`、`interaction history` 等核心字段不变

#### Scenario: reply 提交后统一回到 queued
- **WHEN** 客户端提交合法 reply
- **THEN** 返回 `status=queued`
- **AND** 不存在 sticky 专属 `running` 直连分支

### Requirement: 事件流 cursor/history MUST 使用 FCMP 语义
系统 MUST 统一使用 FCMP `seq` 作为事件重连与历史拉取锚点。

#### Scenario: cursor 续传按 chat_event.seq
- **WHEN** 客户端调用 `/events?cursor=n`
- **THEN** 服务端仅推送 `chat_event.seq > n` 的事件

#### Scenario: events/history 返回 FCMP 序列
- **WHEN** 客户端调用 `/events/history`
- **THEN** 响应事件为 FCMP envelope（`protocol_version=fcmp/1.0`）

### Requirement: reply accepted 后的 queued resume MUST 启动或明确失败
系统 MUST 保证 reply accepted 后进入的 queued resume 不会因为缺失运行资产而无限停留在 `queued`。

#### Scenario: reply accepted 后成功启动 resume
- **WHEN** 客户端提交合法 reply
- **AND** queued resume 所需 run folder 仍然存在
- **THEN** 系统返回 `status=queued`
- **AND** 后续 MUST 启动目标 attempt

#### Scenario: reply accepted 后因缺失 run folder 收敛失败
- **WHEN** 客户端提交合法 reply
- **AND** queued resume 在 redrive 前发现 run folder 已缺失
- **THEN** 系统 MAY 先返回 `status=queued`
- **AND** runtime MUST 随后将该 run 收敛到明确的 `failed`
- **AND** 系统 MUST NOT 让该 run 无限停留在 `queued`

### Requirement: live SSE MUST consume published FCMP rather than materialized audit FCMP
系统 MUST 从 live-published FCMP 直接驱动活跃会话 SSE，而不是等待 `.audit/fcmp_events.*.jsonl` 先物化。

#### Scenario: terminal final message remains visible while audit mirror lags
- **GIVEN** run 已经发布最终 `assistant.message.final`
- **AND** audit FCMP mirror 尚未写盘
- **WHEN** 客户端订阅 `/events`
- **THEN** 仍然 MUST 收到该最终消息

### Requirement: events/history MUST support memory-first replay
系统 MUST 对活跃和近期 run 的 FCMP history 采用 memory-first，audit-fallback。

#### Scenario: recent cursor replays from memory
- **WHEN** 客户端请求近期 cursor 对应的 history
- **THEN** 服务端 MAY 使用 `source=live`
- **AND** MUST NOT 以审计文件物化作为前置

### Requirement: pending and auth status APIs MUST surface current waiting owner
The backend MUST expose the current waiting owner for reconciliation-safe clients.

#### Scenario: client reads pending interaction or auth session status
- **GIVEN** a client reads pending interaction or auth session status
- **WHEN** the run is in a waiting state
- **THEN** the backend MUST expose which current waiting owner is active
- **AND** the response SHOULD expose resume ownership metadata needed for reconciliation-safe refresh

### Requirement: run APIs MUST expose effective execution behavior
The backend MUST expose requested mode, effective mode, and client conversation capability separately.

#### Scenario: client reads status for a normalized run
- **GIVEN** a run request has client-declared conversation metadata
- **WHEN** the backend returns status, pending, or auth-session truth
- **THEN** the response MUST expose requested and effective execution behavior separately
- **AND** the response MUST expose `conversation_mode`
- **AND** clients MUST NOT infer conversation capability from `waiting_auth` or `waiting_user` state names alone

### Requirement: resumed interactive execution MUST expose target-attempt semantics
The backend MUST expose resumed execution as `waiting_* -> queued` followed by a single target-attempt start.

#### Scenario: backend accepts a reply-driven or auth-driven resume
- **GIVEN** the backend accepts a reply-driven or auth-driven resume
- **WHEN** the API-visible state changes are emitted
- **THEN** the transition MUST represent `waiting_* -> queued` first
- **AND** the next `queued -> running` transition MUST correspond to exactly one target attempt

### Requirement: terminal status reads MUST NOT be inferred from stale waiting payloads
API and UI consumers MUST treat terminal status/result as the only terminal truth.

#### Scenario: run reaches a terminal state
- **GIVEN** a run reaches `failed`, `canceled`, or `succeeded`
- **WHEN** API or UI consumers render the terminal result
- **THEN** they MUST read terminal truth from terminal status/result
- **AND** they MUST NOT infer terminal completion from stale pending or history payloads

### Requirement: `interaction/reply` MUST support auth method selection
The `interaction/reply` request payload MUST support auth method selection and auth submission in `mode=auth`.

#### Scenario: client submits auth reply payload
- **GIVEN** a run is in `waiting_auth`
- **WHEN** the client submits `POST /interaction/reply` with `mode=auth`
- **THEN** the payload MUST support selecting auth method
- **AND** the payload MUST support auth submission content

### Requirement: 系统 MUST 提供 auth session 状态接口
The backend MUST provide `GET /v1/jobs/{run_id}/auth/session` for auth timeout and status synchronization.

#### Scenario: client queries auth session status
- **GIVEN** a run is waiting for authentication
- **WHEN** the client requests `GET /v1/jobs/{run_id}/auth/session`
- **THEN** the backend MUST return current auth session status
- **AND** the backend MUST return timeout-related fields

### Requirement: auth submission kinds MUST include callback URL
Auth submission kinds MUST include `callback_url`, `authorization_code`, and `api_key`.

#### Scenario: client submits auth input in chat
- **GIVEN** the client is submitting an auth response through chat
- **WHEN** the backend validates submission kind
- **THEN** it MUST accept `callback_url`
- **AND** it MUST accept `authorization_code` and `api_key`

### Requirement: Live SSE MUST consume published FCMP rather than materialized audit FCMP
The system MUST publish FCMP into a live journal first and MUST deliver active SSE traffic from that live publication path instead of reconstructing FCMP from audit files.

#### Scenario: terminal final message remains visible while audit mirror lags
- **GIVEN** an active or recently terminal run
- **AND** the final audit FCMP file has not been mirrored yet
- **WHEN** the client subscribes to `/events`
- **THEN** the client MUST still receive the published `assistant.message.final`
- **AND** the stream MUST NOT wait for `.audit/fcmp_events.*.jsonl` to appear

### Requirement: events/history MUST support memory-first replay with audit fallback
The system MUST replay active and recently terminal FCMP events from memory first and MUST fall back to audit only when the requested cursor falls outside the live retention window or live memory is unavailable.

#### Scenario: recent cursor replays from memory
- **WHEN** the client calls `/events/history` for a recent cursor on an active or recently terminal run
- **THEN** the response MAY use `source=live`
- **AND** MUST NOT require audit materialization first

#### Scenario: old cursor falls back to audit
- **WHEN** the requested cursor predates the live journal floor or the process has restarted
- **THEN** the response MAY use `source=audit` or `source=mixed`
- **AND** the replayed event order MUST remain FCMP `seq` order

### Requirement: Live SSE MUST expose only canonical conversation lifecycle FCMP
系统 MUST 仅通过 canonical lifecycle FCMP 对外表达 conversation 生命周期，不得继续暴露冗余的 terminal lifecycle 事件。

#### Scenario: terminal lifecycle is represented by state.changed only
- **WHEN** run 进入 `succeeded`、`failed` 或 `canceled`
- **THEN** `/events` MUST 通过 terminal `conversation.state.changed` 表达该生命周期变化
- **AND** MUST NOT 额外发送 `conversation.completed` 或 `conversation.failed`

### Requirement: Live SSE MUST preserve canonical FCMP publish order
系统 MUST 以 canonical FCMP publish order 向 `/events` 推送 active run 的会话事件，且该顺序 MUST NOT 被 audit mirror、history materialization 或 batch backfill 重新定义。

#### Scenario: active SSE follows canonical publish order
- **WHEN** active run 依次发布多条 parser-originated 与 orchestration-originated FCMP
- **THEN** `/events` MUST 按它们的 canonical publish order 推送
- **AND** MUST NOT 因 audit mirror 写盘时序改变相对顺序

### Requirement: events/history MUST preserve the same causal order as live delivery
系统 MUST 保证 `/events/history` 返回的事件顺序与该 run 的 canonical FCMP publish order 一致，即使读取路径采用 memory-first 或 audit fallback。

#### Scenario: history replay matches live order
- **WHEN** 客户端对同一 run 请求某个 cursor 范围内的 `/events/history`
- **THEN** 返回事件顺序 MUST 与该范围内 live delivery 的 canonical order 一致
- **AND** audit fallback MUST NOT 重排已发布事件

### Requirement: Auth guidance MUST precede dependent auth challenge publication
系统 MUST 保证任何依赖用户选择鉴权方式的 challenge/link 发布都晚于对应的 auth 引导事件。

#### Scenario: auth selection guidance precedes challenge link
- **WHEN** run 需要用户先选择鉴权方式再处理 challenge
- **THEN** 面向用户的方式选择引导 MUST 先于 challenge/link 事件可见
- **AND** 用户 MUST NOT 先看到 challenge/link 再看到选择说明

#### Scenario: single-method auth does not surface method selection
- **WHEN** 某条 auth route 只有单一可用方式
- **THEN** API 与 SSE MUST 直接暴露 challenge-active payload
- **AND** MUST NOT 暴露 method-selection UI

### Requirement: Terminal summaries and results MUST NOT outrun canonical terminal lifecycle events
系统 MUST 禁止 terminal summary、terminal result 或等价终态投影在 canonical terminal `conversation.state.changed` 前置条件满足之前对外可见。

#### Scenario: waiting state does not expose terminal result
- **GIVEN** run 仍处于 `waiting_user` 或 `waiting_auth`
- **WHEN** 客户端读取会话事件、summary 或结果投影
- **THEN** 系统 MUST NOT 暴露空的 terminal result 或 terminal summary

#### Scenario: terminal projection waits for terminal state change
- **WHEN** run 进入 terminal
- **THEN** final summary/result 只有在对应 terminal `conversation.state.changed` 前置条件满足后才可见

### Requirement: Waiting-auth resume MUST require canonical auth completion
系统 MUST 仅在 canonical `auth.completed` 之后推进 `waiting_auth -> queued` 与后续 resumed attempt。

#### Scenario: challenge-active polling does not resume
- **WHEN** run 处于 `waiting_auth`
- **AND** 当前 auth session 仍为 non-terminal challenge-active snapshot
- **THEN** repeated detail/list polling MUST NOT issue resume ticket
- **AND** run MUST remain `waiting_auth`

### Requirement: Single-method busy recovery MUST preserve actionable challenge
系统 MUST 在单方式鉴权 busy recovery 时恢复或重投影现有 challenge，而不是推进 resume 或要求重新选择方式。

#### Scenario: single-method busy recovery stays in waiting_auth
- **WHEN** 单方式 auth route 命中已有 active auth session
- **THEN** 用户继续看到当前 challenge
- **AND** 系统 MUST NOT 进入 `queued` 或 `running`

### Requirement: auth input submit MUST record accepted event through schema-aligned orchestrator payload
系统 MUST 在 callback/code 提交被接受时写入合法的 `auth.input.accepted` orchestrator event，并继续后续 auth 处理流程。

#### Scenario: callback URL 提交成功记录 accepted event
- **GIVEN** run 处于 `waiting_auth`
- **WHEN** 客户端提交合法 callback URL
- **THEN** 系统 MUST 写入通过 schema 校验的 `auth.input.accepted`
- **AND** `auth.input.accepted.data` MUST 至少包含 `auth_session_id` 与 `submission_kind`

#### Scenario: canonical accepted timestamp is preserved
- **WHEN** 系统接受 callback URL 或 auth code 输入
- **THEN** 系统 MAY 在 `auth.input.accepted.data` 中记录 canonical `accepted_at`
- **AND** 该字段 MUST 与 runtime schema contract 对齐

#### Scenario: schema drift does not abort accepted auth input with internal error
- **GIVEN** 提交内容本身合法
- **WHEN** 系统处理 auth input submit
- **THEN** auth input 路径 MUST NOT 因 orchestrator event schema 漂移返回 `500`
- **AND** 系统 MUST 继续后续 auth processing 或返回明确的业务错误

### Requirement: opencode high-confidence auth detection MUST enter waiting_auth when request model yields a supported provider
当 `opencode` interactive run 命中高置信度 `auth_required` 时，只要 request-side `engine_options.model` 可以解析出受支持 provider，系统 MUST 进入 `waiting_auth`。

#### Scenario: detection provider missing but request model resolves provider
- **GIVEN** engine 是 `opencode`
- **AND** `auth_detection.provider_id` 为空
- **AND** `engine_options.model` 为 `deepseek/deepseek-reasoner`
- **WHEN** 运行命中高置信度 `auth_required`
- **THEN** run MUST 进入 `waiting_auth`
- **AND** pending auth 的 `provider_id` MUST 为 `deepseek`

#### Scenario: unresolved request model remains diagnosable failure
- **GIVEN** engine 是 `opencode`
- **AND** request-side model 缺失或格式非法
- **WHEN** 运行命中高置信度 `auth_required`
- **THEN** run MAY 失败为 `AUTH_REQUIRED`
- **AND** 系统 MUST 写出 provider unresolved 的明确诊断

### Requirement: Chat windows use canonical chat replay

User-facing interactive chat windows MUST consume canonical chat replay from `/chat` and `/chat/history`, not directly from FCMP `/events`.

#### Scenario: Refresh preserves user replies

- **GIVEN** a run has already recorded user replies and assistant replies
- **WHEN** the client reloads the page and requests `/chat/history`
- **THEN** the returned chat timeline contains the same user and assistant bubbles in the same order as the live chat stream

#### Scenario: Auth submit ordering is stable

- **GIVEN** a user submits auth input during waiting-auth
- **WHEN** the backend publishes canonical chat replay
- **THEN** the user auth-submission bubble appears before the subsequent system resume notice

### Requirement: reply acceptance MUST 经由 canonical backend event path 发布
系统 MUST 在用户 reply 被接受后发布 canonical 的 backend acceptance event，且 canonical chat replay MUST 从这条发布路径派生可见的用户回复气泡。

#### Scenario: accepted reply 通过 canonical replay 对外可见
- **WHEN** 客户端提交一条合法的 interactive reply
- **THEN** 后端 MUST 追加一条 canonical 的 reply-accepted event
- **AND** 可见的用户聊天气泡 MUST 通过 `/chat` 或 `/chat/history` 出现
- **AND** 前端 MUST NOT 在本地自行合成该气泡

