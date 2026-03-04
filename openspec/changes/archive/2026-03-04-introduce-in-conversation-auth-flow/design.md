## Overview

本 change 为 Skill Runner 引入“会话中鉴权”能力。当运行中的会话型 run 命中高置信度 `auth_detection` 时，系统不再直接结束为 `AUTH_REQUIRED` 失败，而是创建与当前 run 绑定的 auth session，并让 canonical run 状态进入新的可恢复态 `waiting_auth`。前端聊天窗口通过新增的 FCMP auth 事件族收到 challenge、链接和输入要求；用户在同一聊天输入框中提交 authorization code 或 API Key，或通过浏览器 callback 完成 OAuth。鉴权完成后，编排器在同一 `run_id`、同一工作目录和执行上下文下，以新的 `attempt` 自动恢复执行。

这是一项 SSOT-first 变更。实现顺序固定为：先状态机与协议合同，再数据模型与持久化，再编排与 auth flow manager 集成，最后才是前端聊天流和恢复执行。这样才能保证 `waiting_auth`、新 auth 事件族、run store 结构和 observability 历史在同一套定义上演进。

## Goals

- 引入 `waiting_auth`，把高置信度 `auth_detection` 升级为可恢复的会话内鉴权。
- 复用现有 `engine_auth_flow_manager`，不再设计第二套 engine auth 状态机。
- 在 FCMP 中新增 auth 事件族，并保证其 ordering 与 canonical state transition 一致。
- 允许聊天窗口内提交 authorization code / API Key，并保证 raw secret 不落盘、不回显、不进入事件历史。
- 鉴权成功后，以同一 `run_id`、同一环境、新 `attempt` 恢复执行。

## Non-Goals

- 不修改 provider 自身鉴权协议。
- 不把 `medium/low` `auth_detection` 升级为 `waiting_auth`。
- 不为 headless run 引入新的 auth 会话恢复行为。
- 不新增管理台或独立 auth UI。

## Architecture

### Canonical state and transitions

新增 canonical state：`waiting_auth`

更新后的 canonical states：
- `queued`
- `running`
- `waiting_user`
- `waiting_auth`
- `succeeded`
- `failed`
- `canceled`

新增 canonical transitions：
- `running -> waiting_auth` on `auth.required`
- `waiting_auth -> waiting_auth` on `auth.input.accepted`
- `waiting_auth -> waiting_auth` on `auth.challenge.updated`
- `waiting_auth -> queued` on `auth.completed`
- `waiting_auth -> failed` on `auth.failed`
- `waiting_auth -> canceled` on `run.cancelled`

关键约束：
- `waiting_auth` 是非终态、可恢复态。
- `auth.completed` 不直接回 `running`，而是先回 `queued`，再由 orchestrator 申请槽位、启动新 attempt。
- `waiting_user` 与 `waiting_auth` 语义严格分离，不能共用 pending payload。

### FCMP and RASP event families

新增 FCMP 事件：
- `auth.required`
- `auth.challenge.updated`
- `auth.input.accepted`
- `auth.completed`
- `auth.failed`

FCMP ordering 固定为：
1. 进入 auth：`auth.required` -> `conversation.state.changed(running -> waiting_auth, trigger=auth.required)`
2. 用户提交 auth 输入：`auth.input.accepted`
3. challenge 更新：`auth.challenge.updated`
4. auth 成功：`auth.completed` -> `conversation.state.changed(waiting_auth -> queued, trigger=auth.completed)` -> 新 attempt 正常启动事件
5. auth 不可恢复失败：`auth.failed` -> `conversation.state.changed(waiting_auth -> failed, trigger=auth.failed)` -> `conversation.failed`

RASP / 审计新增内部事件：
- `AUTH_SESSION_CREATED`
- `AUTH_INPUT_RECEIVED`
- `AUTH_INPUT_REDACTED`
- `AUTH_SESSION_COMPLETED`
- `AUTH_SESSION_FAILED`
- `AUTH_RESUME_SCHEDULED`

### Run-scoped auth orchestration

新增 `server/services/orchestration/run_auth_orchestration_service.py`，作为 run 与 auth session 的绑定层。它只负责：
- 根据 `AuthDetectionResult` 构造 auth session
- 将 `run_id / attempt / engine / provider_id / workspace context` 绑定到 auth session
- 接收聊天内 auth 输入或 OAuth callback 成功通知
- auth 成功后清理 pending auth，写入 provenance，并调度新 attempt

`engine_auth_flow_manager` 继续是 engine 级 auth 的唯一 canonical 实现，负责：
- challenge 生成
- OAuth callback 协调
- auth code / API key 提交
- session-level completion / failure

禁止在 orchestrator 或 UI 中复制 provider auth 协议逻辑。

### Data model and persistence

#### 新增模型
- `PendingAuth`
- `AuthChallenge`
- `AuthReplyRequest`
- `AuthSessionBinding`
- `AuthResumeContext`

#### 持久化扩展
`run_store` 新增：
- `pending_auth`
- `auth_resume_context`
- `auth_session_id`
- `resumed_from_attempt`
- `resume_reason`

兼容性要求：
- 旧 run 记录无 `pending_auth` 字段时必须兼容读取
- 旧 history / observability 行为不回归

### Resume semantics

auth 成功恢复固定采用：
- 同一 `run_id`
- 同一工作目录 / run_dir / skill context / request payload
- 新 `attempt = previous_attempt + 1`

恢复前必须清理：
- `pending_auth`
- `pending_interaction`（若残留）
- auth-blocked session handle
- 临时 auth submission 缓存
- 旧的 forced auth failure marker

新 attempt 必须记录 provenance：
- `resume_reason = "auth_completed"`
- `resumed_from_attempt = <N>`
- `auth_session_id = <...>`

### Chat input and redaction model

首波继续复用现有聊天回复路径：
- `POST /v1/jobs/{run_id}/interaction/reply`

请求模型扩展为 union：
- `mode=interaction`
- `mode=auth`

当 `mode=auth` 时：
- 不写普通用户消息
- 不进入 generic interaction reply path
- 直接交给 `run_auth_orchestration_service`
- raw `submission.value` 在进入事件/审计前必须立刻 redaction

前端聊天区只显示本地合成的占位消息，例如：
- `Authorization code submitted`
- `API key submitted`

禁止 raw authorization code / API key 出现在：
- FCMP history
- `.audit/meta`
- parser diagnostics
- user messages

### Headless compatibility

只有会话型、由聊天客户端承接 FCMP 的 run 才启用 `waiting_auth` 流程。首波默认将 `execution_mode=interactive` 作为会话 run 的最低门槛；后续若有更细粒度的客户端能力标记，可以再增量收敛。

以下场景继续保持旧行为：
- headless / 非会话 run
- `auth_detection` 只有 `medium/low`
- 无可用 auth flow 构造器
- auth session 创建失败

## Risks and Mitigations

### 风险：`waiting_auth` 与 `waiting_user` 语义混淆
对策：
- 单独新增 canonical state 和 FCMP 事件族
- `PendingAuth` 与 `PendingInteraction` 严格分离
- 协议、状态机和 UI 都不复用 generic waiting_user 语义

### 风险：raw secret 泄漏到历史或审计
对策：
- auth 输入走专门的 `mode=auth`
- 服务端收到后立刻 redaction
- 单测覆盖 FCMP、审计、诊断和聊天历史四条路径

### 风险：恢复执行破坏既有 attempt 语义
对策：
- 固定为同 run、新 attempt
- provenance 字段显式化
- runtime 必跑清单覆盖 seq/state/history 不变量

### 风险：headless 行为回归
对策：
- 将 `waiting_auth` 明确限制在会话型 run
- 对非会话 run 保持 `AUTH_REQUIRED` 失败语义
- 新增专门兼容测试

## Validation

- runtime 必跑清单：
  - `tests/unit/test_session_invariant_contract.py`
  - `tests/unit/test_session_state_model_properties.py`
  - `tests/unit/test_fcmp_mapping_properties.py`
  - `tests/unit/test_protocol_state_alignment.py`
  - `tests/unit/test_protocol_schema_registry.py`
  - `tests/unit/test_runtime_event_protocol.py`
  - `tests/unit/test_run_observability.py`
- 若触达 seq/cursor/history，追加 `tests/unit/test_fcmp_cursor_global_seq.py`
- 若 auth 事件进入 paired interaction 语义，追加 `tests/unit/test_fcmp_interaction_dedup.py`
- 新增 auth 相关测试：
  - `tests/unit/test_run_auth_orchestration_service.py`
  - `tests/unit/test_in_conversation_auth_statechart.py`
  - `tests/unit/test_in_conversation_auth_protocol_mapping.py`
  - `tests/unit/test_in_conversation_auth_resume.py`
  - `tests/unit/test_in_conversation_auth_redaction.py`
  - `tests/api_integration/test_chat_auth_flow.py`
- mypy：
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/services/orchestration/run_job_lifecycle_service.py`
  - `server/services/orchestration/run_store.py`
  - `server/services/engine_management/engine_auth_flow_manager.py`
  - `server/runtime/protocol/event_protocol.py`
  - `server/runtime/protocol/factories.py`
  - `server/runtime/observability/run_observability.py`
  - `server/models/common.py`
  - `server/models/interaction.py`
  - `server/models/runtime_event.py`
