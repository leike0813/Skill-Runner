# interactive-job-api Specification

## Purpose
定义任务执行模式选择、待决交互查询和交互回复提交的 API 约束。
## Requirements
### Requirement: local runtime mode MUST provide lease lifecycle APIs
系统在 `SKILL_RUNNER_RUNTIME_MODE=local` 下 MUST 提供 lease acquire/heartbeat/release API，用于插件保活与异常退出回收。

#### Scenario: acquire lease in local mode
- **GIVEN** runtime mode is `local`
- **WHEN** 客户端调用 `POST /v1/local-runtime/lease/acquire`
- **THEN** 系统返回 `lease_id`、`ttl_seconds`、`expires_at`

#### Scenario: heartbeat renews lease
- **GIVEN** lease 已获取且未过期
- **WHEN** 客户端调用 `POST /v1/local-runtime/lease/heartbeat`
- **THEN** 租约过期时间被续期

#### Scenario: all leases gone triggers local self-stop
- **GIVEN** local runtime 至少出现过一个 lease
- **WHEN** 当前所有 lease 已释放或过期
- **THEN** runtime MAY 触发本地自停

#### Scenario: lease APIs unavailable outside local mode
- **WHEN** runtime mode is not `local`
- **THEN** `local-runtime/lease/*` 请求返回 `409`

### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: Skill 默认 runtime options 参与 effective options 合成
- **GIVEN** skill 在 `runner.json.runtime.default_options` 声明了默认 runtime options
- **WHEN** 客户端调用 `POST /v1/jobs`
- **THEN** 系统 MUST 先应用 skill 默认值，再应用请求值覆盖
- **AND** `effective_runtime_options` 反映合成结果

#### Scenario: 请求值覆盖 skill 默认值
- **GIVEN** skill 默认值与请求体对同一 runtime option 都有声明
- **WHEN** 系统构建 `effective_runtime_options`
- **THEN** 请求体值 MUST 覆盖 skill 默认值

#### Scenario: skill 默认值非法时忽略并告警
- **GIVEN** `runner.json.runtime.default_options` 中存在未知键或非法值
- **WHEN** 系统执行 runtime option 合成
- **THEN** 系统 MUST 忽略该默认值
- **AND** MUST 记录可观测 warning（日志 + lifecycle warning/diagnostic）
- **AND** MUST NOT 因该默认值阻断 run

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

### Requirement: skill asset reads MUST follow the shared declaration-plus-fallback resolver
Runtime schema validation, artifact inference, and management schema reads MUST use the same skill asset resolution behavior.

#### Scenario: management schema read follows fallback
- **GIVEN** `runner.json.schemas.output` is missing
- **AND** `assets/output.schema.json` exists
- **THEN** management schema inspection MUST read the fallback file successfully

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

### Requirement: jobs create API MUST accept declarative file input paths
The `POST /v1/jobs` API MUST accept file-sourced input values in the request body as `uploads/`-relative paths.

#### Scenario: create request carries inline and file inputs together
- **WHEN** a client submits mixed inline and file inputs in `input`
- **THEN** the backend accepts both in the same payload
- **AND** file values are treated as uploads-relative path references

### Requirement: runtime.dependencies MUST be attempted before agent command execution
系统 MUST 在 agent 命令执行前尝试根据 skill manifest `runtime.dependencies` 注入运行时依赖。

#### Scenario: dependency injection probe succeeds
- **GIVEN** skill manifest 声明了 `runtime.dependencies`
- **WHEN** backend 开始执行该 turn
- **THEN** backend MUST 先完成依赖注入探测
- **AND** probe 成功后 MUST 以注入后的命令执行 agent

#### Scenario: dependency injection probe fails with best-effort fallback
- **GIVEN** skill manifest 声明了 `runtime.dependencies`
- **WHEN** backend 依赖注入探测失败
- **THEN** backend MUST 写入可观测 warning
- **AND** backend MUST 回退执行原始 agent 命令（best-effort）

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

### Requirement: Jobs API MUST support unified request source

`POST /v1/jobs` MUST support a unified request source contract for installed skill and temp upload skill.

#### Scenario: create installed request from unified endpoint
- **WHEN** client calls `POST /v1/jobs` with `skill_source=installed` and `skill_id`
- **THEN** system MUST create request in unified request store
- **AND** response MUST return `request_id`

#### Scenario: create temp-upload request from unified endpoint
- **WHEN** client calls `POST /v1/jobs` with `skill_source=temp_upload`
- **THEN** system MUST create request in unified request store
- **AND** response MUST return `request_id`

### Requirement: Upload entry MUST be unified under jobs API

System MUST use `POST /v1/jobs/{request_id}/upload` as the only upload entry for both installed and temp-upload requests.

#### Scenario: temp upload request accepts skill package
- **GIVEN** request source is `temp_upload`
- **WHEN** client uploads package via `POST /v1/jobs/{request_id}/upload`
- **THEN** system MUST validate and stage package in request lifecycle

#### Scenario: installed request accepts input upload
- **GIVEN** request source is `installed`
- **WHEN** client uploads input zip via `POST /v1/jobs/{request_id}/upload`
- **THEN** system MUST build input manifest and continue standard dispatch flow

#### Scenario: temp upload creates run from parsed manifest without installed registry lookup
- **GIVEN** request source is `temp_upload`
- **AND** backend has parsed a valid skill manifest from uploaded package
- **WHEN** upload flow creates run
- **THEN** run creation MUST use the parsed manifest directly
- **AND** MUST NOT require installed skill registry lookup for the uploaded skill id

### Requirement: Legacy temp-skill-runs API MUST be removed

System MUST remove `/v1/temp-skill-runs/*` routes after unified jobs entry is active.

#### Scenario: temp-skill-runs endpoint is unavailable
- **WHEN** client calls any `/v1/temp-skill-runs/*` endpoint
- **THEN** system MUST return endpoint-not-found behavior

### Requirement: Upload orchestration MUST expose request-scoped trace milestones

Interactive jobs upload path MUST emit structured trace milestones so operators can identify where a request stopped before run binding or dispatch.

#### Scenario: cache hit upload path is fully traceable
- **WHEN** upload path resolves a cache hit
- **THEN** backend MUST emit `upload.cache.hit`
- **AND** the event MUST include `request_id` and cached `run_id`

#### Scenario: cache miss upload path is fully traceable
- **WHEN** upload path creates and binds a new run
- **THEN** backend MUST emit `upload.run.created` and `upload.request_run.bound`
- **AND** events MUST preserve the same `request_id`

### Requirement: Interaction/auth transitions MUST be traceable with stable event codes

Interactive reply and in-conversation auth handling MUST emit stable structured trace events for accepted/rejected replies and auth progression.

#### Scenario: reply rejected trace
- **WHEN** interaction reply is rejected due to stale or invalid state
- **THEN** backend MUST emit `interaction.reply.rejected`
- **AND** the event MUST include `request_id` and a stable rejection code

#### Scenario: auth completion trace
- **WHEN** auth submission completes and resume ticket is issued
- **THEN** backend MUST emit `auth.completed`
- **AND** the event MUST include `request_id`, `run_id`, and the resume ticket id

### Requirement: Temporary skill upload SHALL remain on unified jobs API
Temporary skill upload runs SHALL use the unified `/v1/jobs` create/upload flow and SHALL NOT require a separate temp-skill API family.

#### Scenario: Legacy temp-skill endpoint access
- **WHEN** a client calls `/v1/temp-skill-runs/*`
- **THEN** the API SHALL return not found semantics (404)

### Requirement: Upload staging SHALL be runtime-internal and data-dir scoped
During `/v1/jobs/{request_id}/upload`, temporary extraction staging SHALL occur under server data root and be cleaned up after upload flow completion.

#### Scenario: Upload staging and cleanup
- **WHEN** upload processing starts for a request
- **THEN** the server SHALL stage files under `data/tmp_uploads/<request_id>`
- **AND** after success or failure, the server SHALL perform best-effort deletion of that request staging directory

### Requirement: 文件预览响应 MUST 支持格式化扩展字段
文件预览接口 MUST 在保持现有核心字段兼容的前提下，支持更丰富的文本格式识别与渲染增强。

#### Scenario: 扩展格式识别
- **WHEN** 客户端请求文件预览
- **THEN** 系统可识别 `json|yaml|toml|python|javascript|markdown|text`
- **AND** 返回结果保持原有字段兼容

#### Scenario: 渲染失败回退
- **WHEN** 某格式高亮渲染失败或依赖不可用
- **THEN** 接口返回普通文本预览
- **AND** 客户端仍可无中断展示内容

### Requirement: E2E Run 文件预览 MUST 可滚动并按格式渲染
E2E Run 页文件预览 MUST 支持长内容滚动，并根据预览格式渲染 Markdown / JSON。

#### Scenario: 长内容文件
- **WHEN** 预览内容超出容器高度
- **THEN** 用户可在预览面板内纵向滚动

#### Scenario: Markdown / JSON 文件
- **WHEN** 预览结果包含 `detected_format = markdown|json`
- **THEN** 前端使用对应渲染分支展示内容
- **AND** 非 markdown/json 保持文本分支

### Requirement: 管理观测接口 MUST 支持 Run Scope 时间线聚合
管理侧接口 MUST 提供基于 run 范围的统一时序聚合数据，用于跨 Orchestrator、RASP、FCMP、Chat、Client 的单时间线渲染。

#### Scenario: 默认返回最近窗口
- **WHEN** 客户端请求 timeline history 且未提供 cursor
- **THEN** 系统返回最近窗口事件（默认 100 条）
- **AND** 返回 cursor floor/ceiling 用于后续增量拉取

#### Scenario: cursor 增量拉取
- **WHEN** 客户端提供 cursor
- **THEN** 系统仅返回 timeline_seq 大于该 cursor 的事件
- **AND** 事件顺序稳定并可连续消费

### Requirement: E2E 客户端代理 MUST 支持 run bundle 下载透传
E2E 客户端代理层 MUST 提供 run bundle 下载透传能力，以稳定消费后端 run bundle API。

#### Scenario: proxy returns backend bundle as attachment
- **WHEN** 客户端调用 `/api/runs/{request_id}/bundle/download`
- **THEN** 代理 MUST 从后端获取 run bundle 二进制
- **AND** 以 zip 附件响应返回给浏览器

#### Scenario: proxy preserves backend error semantics
- **WHEN** 后端返回 run 不存在、bundle 生成失败或网络不可达
- **THEN** 代理 MUST 返回受控错误响应
- **AND** 错误映射行为与现有 E2E 代理一致

### Requirement: Jobs result artifact paths MUST be canonicalized after repair
当服务通过 artifact path autofix 成功修复输出路径后，对外输出中的 artifact 路径 MUST 使用 canonical `artifacts/...` 形式，避免客户端读取到错误目录路径。

#### Scenario: repaired output returns canonical artifact path
- **GIVEN** agent 最终输出中的 artifact 路径最初位于错误目录
- **AND** 服务成功执行 artifact path autofix
- **WHEN** 读取 run 结果与 artifacts 列表
- **THEN** 响应中的 artifact 路径 MUST 指向 canonical `artifacts/...`
- **AND** 不应继续暴露旧错误路径

### Requirement: 系统 MUST 提供 jobs 主链路 run 文件树读取接口
系统 MUST 提供 `GET /v1/jobs/{request_id}/files`，用于返回当前 run 的可浏览文件树条目。

#### Scenario: 客户端读取 run 文件树
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/files`
- **THEN** 服务返回 run scope 的文件树条目列表
- **AND** 每个条目至少包含 `path/name/is_dir/depth`

### Requirement: 系统 MUST 提供 jobs 主链路 run 文件预览接口
系统 MUST 提供 `GET /v1/jobs/{request_id}/file?path=...`，并返回后端 canonical 预览载荷。

#### Scenario: 客户端读取文本文件预览
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/file?path=...`
- **THEN** 服务返回 `preview` 载荷
- **AND** 载荷包含兼容字段 `mode/content/meta/size`
- **AND** 载荷可选包含扩展字段 `detected_format/rendered_html/json_pretty`

#### Scenario: 非法路径请求被拒绝
- **WHEN** 客户端传入绝对路径、`..` 或无效路径
- **THEN** 服务返回 `400`
- **AND** 不读取 run 目录外文件

### Requirement: waiting_auth MUST support import as a conversation auth method
当会话鉴权策略声明 `import` 时，交互式 run 在 `waiting_auth` 阶段 MUST 允许通过文件导入完成鉴权。

#### Scenario: auth import is accepted and resumes run
- **GIVEN** run 当前状态为 `waiting_auth`
- **AND** pending auth method selection 包含 `import`
- **WHEN** client 调用 `POST /v1/jobs/{request_id}/interaction/auth/import` 并上传通过校验的文件
- **THEN** backend MUST 清理 pending auth 状态并发出 `auth.session.completed`
- **AND** run MUST 进入 queued/running 恢复路径

#### Scenario: auth import is rejected when method is unavailable
- **GIVEN** run 不在 `waiting_auth` 或当前可用方法不包含 `import`
- **WHEN** client 调用导入接口
- **THEN** backend MUST 返回可诊断错误（409/422）
- **AND** MUST NOT 改写当前 pending 状态

### Requirement: Interactive run MUST transition to waiting_auth for blocked OAuth prompts
交互式运行中，当 CLI 出现 OAuth 授权码阻塞提示并被 runtime 判定为高置信鉴权需求时，系统 MUST 自动转入 `waiting_auth`，而不是长期停留在 `running`。

#### Scenario: gemini oauth code prompt blocks process
- **GIVEN** Gemini CLI 输出授权 URL 与授权码输入提示
- **AND** 进程未退出且进入阻塞等待输入
- **WHEN** runtime auth detection 命中并触发 early-exit
- **THEN** run MUST 进入 `waiting_auth`
- **AND** 现有会话鉴权恢复路径 MUST 继续可用

### Requirement: interactive run 的鉴权等待触发 MUST 与 parser auth signal 一致
交互式 run 在进入 `waiting_auth` 时，后端 MUST 基于 parser `auth_signal` 的统一语义决策，避免 parser 与 detection 双层漂移。

#### Scenario: parser signal drives auth-required terminal mapping
- **GIVEN** run 的运行流解析结果包含 `auth_signal`
- **WHEN** 交互式 run 完成本轮终态归一化
- **THEN** 后端 MUST 依据该信号计算鉴权分类并决定是否进入 `waiting_auth`
- **AND** 不应再依赖独立 rule-registry 对 `combined_text/diagnostics` 二次匹配

### Requirement: interactive waiting_auth trigger MUST be high-confidence only
Interactive run auth gating MUST only treat `auth_signal.confidence=high` as waiting-auth trigger input.

#### Scenario: low-confidence signal does not change waiting_auth semantics
- **GIVEN** interactive run has `auth_signal.required=true` with `confidence=low`
- **WHEN** backend evaluates terminal mapping for interactive run
- **THEN** backend MUST keep the signal as diagnostic-only and MUST NOT transition to `waiting_auth` from it.

### Requirement: ask_user MUST support upload_files as a first-class kind
交互提示模型 MUST 支持 `kind=upload_files`，并通过统一 `files[]` 描述文件选择需求。

#### Scenario: pending_auth import challenge carries upload_files hint
- **GIVEN** run 处于 `waiting_auth`
- **AND** challenge kind 为 `import_files`
- **WHEN** 客户端查询 pending 交互
- **THEN** `pending_auth.ask_user.kind` MUST be `upload_files`
- **AND** `pending_auth.ask_user.files` MUST describe required/optional file items

### Requirement: upload_files parse failure MUST NOT block core runtime flow
`ask_user` 仅作为 UI hint；即使 `upload_files` hint 解析失败，核心运行状态机 MUST 保持可恢复，不得因此崩溃。

#### Scenario: malformed upload_files hint
- **WHEN** 前端无法正确解析 `ask_user.files`
- **THEN** 服务端核心状态机仍保持 `waiting_auth` 可恢复

### Requirement: protocol history MUST allow Gemini parsed JSON events
管理端协议历史中的 RASP 流 MUST 支持 `parsed.json` 事件类型，用于承载 Gemini 的整段 JSON 解析结果。

#### Scenario: parsed JSON event in RASP history
- **WHEN** Gemini parser 从 stdout/stderr 成功解析出整段 JSON
- **THEN** `GET /v1/management/runs/{request_id}/protocol/history?stream=rasp` 返回中 MAY 包含 `event.type = parsed.json`
- **AND** 该事件 `data` MUST 至少包含 `stream`

### Requirement: raw line payload MUST remain string-compatible after parser coalescing
Gemini parser 归并后的 `raw.stdout/raw.stderr` 事件 `data.line` MUST 仍保持字符串（可多行）。

#### Scenario: coalesced stderr block
- **WHEN** 连续 stderr 行被归并为块
- **THEN** 事件类型仍为 `raw.stderr`
- **AND** `data.line` MUST be a string containing newline-separated content

### Requirement: protocol history behavior MUST remain wire-compatible under single-source publishing
收敛到 live publisher 单源后，`protocol/history` 的外部接口 MUST 保持兼容。

#### Scenario: client polls protocol history during and after run completion
- **GIVEN** 客户端在 running 与 terminal 阶段轮询 `protocol/history`
- **WHEN** 读取 `stream=fcmp|rasp`
- **THEN** 响应字段形状 MUST 与既有接口兼容
- **AND** terminal 阶段 `source` 仍表示 `audit` 口径。

### Requirement: management protocol history MUST support bounded result windows
管理端协议历史查询 MUST 支持可选 `limit` 参数以限制返回事件数量。

#### Scenario: default bounded window
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history` 且不传 `limit`
- **THEN** 服务端 MUST 返回最近窗口（默认 200 条）

#### Scenario: incremental bounded window
- **GIVEN** 客户端传入 `from_seq`
- **WHEN** 同时传入 `limit`
- **THEN** 服务端 MUST 保持增量语义并按 `limit` 进行上限截断

### Requirement: raw event payload MUST remain string-compatible after coalescing
RASP `raw.stdout/raw.stderr` 的 `data.line` 字段 MUST 保持 `string` 类型，允许多行块文本。

#### Scenario: coalesced raw stderr block
- **WHEN** 后端将多条连续 stderr 行归并
- **THEN** 事件类型仍为 `raw.stderr`
- **AND** `data.line` MUST be a string containing newline-separated content

### Requirement: live and audit raw transformations MUST share one canonicalization rule
运行期 live 发布与终态审计重建在 raw 分块上 MUST 复用同一 canonicalization 规则，避免前后观测结果漂移。

#### Scenario: same raw input observed in live and terminal views
- **WHEN** 同一 run 在运行期和终态分别读取 RASP raw 事件
- **THEN** raw 分块边界规则 MUST 一致
- **AND** 不得出现“仅 live 逐行拆分、终态分块”的双轨行为

### Requirement: FCMP MUST expose generic assistant process events before final convergence
系统 MUST 支持在 FCMP 中发布通用过程事件（非引擎专属）并在收敛时发布 promoted/final。

#### Scenario: process-first then final
- **GIVEN** engine 在同一回合输出多条中间消息
- **WHEN** runtime 处理该回合流式输出
- **THEN** 系统 MUST 先发布 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`（按实际类型）
- **AND** 在回合结束信号到达后发布 `assistant.message.promoted` 与 `assistant.message.final`

### Requirement: failed/canceled MUST NOT fallback promote assistant final
The runtime MUST NOT emit fallback `assistant.message.final` when status is `failed` or `canceled`.

#### Scenario: failed terminal without turn-end signal
- **GIVEN** run 终态为 `failed` 或 `canceled`
- **AND** 没有可用于收敛的回合结束信号
- **WHEN** FCMP 生成终态事件
- **THEN** 系统 MUST NOT 通过 fallback 生成 `assistant.message.final`

### Requirement: chat history API MUST expose assistant process rows for FCMP process events
系统 MUST 将 FCMP 的 assistant 过程事件映射为 chat history 可消费条目，且不新增路由。

#### Scenario: process events in chat history
- **GIVEN** FCMP 流包含 `assistant.reasoning`、`assistant.tool_call`、`assistant.command_execution`
- **WHEN** 客户端读取 `/chat/history`
- **THEN** 返回事件 MUST 包含 `role=assistant` 且 `kind=assistant_process` 的条目
- **AND** 条目 SHOULD 在 correlation 中包含 `process_type`、`message_id`（若有）与 `fcmp_seq`

### Requirement: promoted event MUST NOT be rendered as standalone chat body
系统 MUST NOT 将 `assistant.message.promoted` 导出为独立聊天正文条目。

#### Scenario: promoted boundary only
- **GIVEN** FCMP 流包含 `assistant.message.promoted`
- **WHEN** 生成 chat replay 历史
- **THEN** 该事件 MUST 仅作为收敛边界语义使用
- **AND** MUST NOT 生成额外聊天正文文本条目

### Requirement: Waiting interaction persistence MUST require a persisted session handle
交互 run 在进入 `waiting_user` 持久化时 MUST 已存在可恢复会话句柄，系统 MUST NOT 再从 raw 输出临时提取。

#### Scenario: waiting_user with eventized handle available
- **GIVEN** 引擎在运行期已发布并持久化 `lifecycle.run_handle`
- **WHEN** orchestrator 持久化 `waiting_user` 交互数据
- **THEN** 系统 MUST 直接复用已持久化 handle
- **AND** MUST NOT 调用 `extract_session_handle(raw_output, ...)`

#### Scenario: waiting_user without persisted handle
- **GIVEN** run 进入 `waiting_user` 分支前未持久化 session handle
- **WHEN** orchestrator 执行 waiting interaction 持久化
- **THEN** 系统 MUST 返回 `SESSION_RESUME_FAILED`
- **AND** run MUST NOT 以 waiting_user 继续挂起

### Requirement: FCMP event surface remains stable without assistant turn markers
FCMP 对外事件集合 MUST 保持稳定，不新增 `assistant.turn_*` 事件类型。

#### Scenario: rasp turn markers present
- **GIVEN** RASP 流中存在 `agent.turn_start` / `agent.turn_complete`
- **WHEN** 系统映射并发布 FCMP 事件
- **THEN** FCMP MUST NOT 发布任何 `assistant.turn_*` 事件
- **AND** 现有 `assistant.reasoning/tool_call/command_execution/promoted/final` 语义保持不变

### Requirement: Session handle persistence SHOULD prefer live run-handle events
运行链路在具备事件化 run-handle 时 MUST 优先即时持久化，不依赖 waiting 阶段的延迟提取。

#### Scenario: eventized engine publishes run handle during running
- **GIVEN** 运行中的 attempt 发布 `lifecycle.run_handle`
- **WHEN** run lifecycle 消费该事件
- **THEN** 系统 MUST 立即持久化 engine session handle
- **AND** 后续 resume 读取 SHOULD 可直接获取该 handle

#### Scenario: non-eventized engine fallback remains available
- **GIVEN** 引擎当前不发布 `lifecycle.run_handle`
- **WHEN** run 进入 waiting interaction 持久化阶段
- **THEN** 系统 MAY 使用 `extract_session_handle(...)` 回退提取
- **AND** 回退路径 MUST 保持向后兼容

### Requirement: Jobs API MUST expose dedicated debug bundle route
系统 MUST 提供独立的 debug bundle 下载接口，不通过 query 参数复用普通 bundle 路由。

#### Scenario: download debug bundle from jobs api
- **WHEN** 客户端请求 `GET /v1/jobs/{request_id}/bundle/debug`
- **AND** run 处于可下载状态
- **THEN** 响应返回 debug bundle zip 文件
- **AND** 不影响 `GET /v1/jobs/{request_id}/bundle` 的普通 bundle 语义

### Requirement: runtime.dependencies wrapping MUST preserve normalized spawn command
系统在执行 `runtime.dependencies` 注入包装时 MUST 以归一化后的命令作为 base command，不得回退到归一化前命令。

#### Scenario: Windows npm cmd shim remains normalized after dependency wrapping
- **GIVEN** Windows 平台上原始命令首参数为 npm `.cmd` shim
- **AND** 系统已得到归一化命令 `node <entry.js> ...`
- **WHEN** `runtime.dependencies` probe 成功并执行 `uv run` 包装
- **THEN** 最终执行 argv MUST 基于归一化命令拼接（`uv run ... -- node <entry.js> ...`）
- **AND** 最终执行 argv MUST NOT 回退为 `.cmd` shim 形式

#### Scenario: best-effort fallback still uses normalized base command
- **GIVEN** Windows 平台命令已完成归一化
- **WHEN** `runtime.dependencies` probe 失败并走 best-effort fallback
- **THEN** 系统 MUST 继续执行归一化命令
- **AND** MUST NOT 因 probe 失败恢复原始未归一化命令

### Requirement: Windows spawn argv MUST avoid cmd-shim truncation semantics
系统在 Windows 上执行 engine 命令时 MUST 避免经由 npm `.cmd` shim 的 `cmd.exe` 二次参数解析路径，以防复杂参数被截断或改写。

#### Scenario: quoted prompt and path args remain intact after normalization
- **GIVEN** Windows 平台下原始命令包含带空格、引号或反斜杠的 prompt/path 参数
- **WHEN** 系统执行命令归一化并启动子进程
- **THEN** 最终执行 argv MUST 通过 `node <entry.js> ...` 直启路径传递
- **AND** 参数项数量与顺序 MUST 与归一化输入一致
- **AND** 参数值 MUST NOT 被截断、拆分或重写

### Requirement: local runtime lease MUST provide first-heartbeat grace window
系统在 local runtime lease 生命周期中 MUST 提供首次心跳宽限窗口，以覆盖慢启动阶段的首次心跳延迟；该能力不得改变现有 lease API 字段结构。

#### Scenario: lease does not expire during first-heartbeat grace
- **GIVEN** 客户端刚完成 `POST /v1/local-runtime/lease/acquire`
- **AND** 尚未发送首次 heartbeat
- **WHEN** 过期判定发生在 `ttl + first_heartbeat_grace` 窗口内
- **THEN** 系统不得将该 lease 判定为过期

#### Scenario: post-first-heartbeat returns to normal ttl
- **GIVEN** lease 已收到首次 heartbeat
- **WHEN** 后续过期判定执行
- **THEN** 系统按常规 TTL 续租语义判定过期
- **AND** 不再应用首次心跳宽限

### Requirement: 本地运行模式 MUST 支持插件租约心跳生命周期
系统在 `SKILL_RUNNER_RUNTIME_MODE=local` 下 MUST 提供 lease acquire/heartbeat/release API，以支持插件进程生命周期对本地服务进行保活和回收控制。

#### Scenario: local lease acquire and heartbeat
- **GIVEN** runtime mode is `local`
- **WHEN** 客户端调用 `POST /v1/local-runtime/lease/acquire`
- **THEN** 系统返回 `lease_id`、`ttl_seconds`、`expires_at`
- **AND** 后续 `heartbeat` 可续期同一 lease

#### Scenario: lease expiry triggers local shutdown
- **GIVEN** 本地服务已出现过至少一个 lease
- **AND** 当前所有 lease 已过期或被释放
- **WHEN** 超过 TTL 且无新 lease
- **THEN** 系统触发本地服务自停

#### Scenario: lease API rejected outside local mode
- **WHEN** runtime mode is not `local`
- **THEN** `acquire/heartbeat/release` 接口返回 `409`

