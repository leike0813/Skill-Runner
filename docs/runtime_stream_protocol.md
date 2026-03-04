# Runtime Stream Protocol (FCMP Single-Stream)

## 1. Overview

Skill Runner 对外运行时事件流收敛为 FCMP 单流：

- `FCMP/1.0`：客户端唯一业务消费协议（SSE `event=chat_event`）。
- `RASP/1.0`：仅用于后端审计与证据保留，不作为客户端消费契约。

补充：

- 聊天气泡渲染已从 FCMP 解耦，改由独立的 canonical chat replay `/chat` 与 `/chat/history` 提供。
- `/events` 与 `/events/history` 继续服务 runtime observability / protocol consumer，不再作为聊天窗口 SSOT。

## 2. FCMP Envelope

每条 `chat_event` 载荷结构：

```json
{
  "protocol_version": "fcmp/1.0",
  "run_id": "run-xxx",
  "seq": 5,
  "ts": "2026-02-24T12:34:56.000000",
  "engine": "codex",
  "type": "assistant.message.final",
  "data": {},
  "meta": {
    "attempt": 2,
    "local_seq": 3
  },
  "raw_ref": null
}
```

## 3. FCMP Event Types

- `conversation.state.changed`
- `assistant.message.final`
- `user.input.required`
- `auth.required`
- `auth.challenge.updated`
- `auth.input.accepted`
- `auth.completed`
- `auth.failed`
- `interaction.reply.accepted`
- `interaction.auto_decide.timeout`
- `diagnostic.warning`
- `raw.stdout` / `raw.stderr`

### 3.1 `conversation.state.changed`

```json
{
  "type": "conversation.state.changed",
  "data": {
    "from": "running",
    "to": "waiting_auth",
    "trigger": "auth.required",
    "updated_at": "2026-02-24T12:34:56.000000",
    "pending_interaction_id": null,
    "pending_auth_session_id": "auth-session-123"
  }
}
```

说明：

- `pending_interaction_id` 仅在 `waiting_user` 转移中携带；
- `pending_auth_session_id` 仅在 `waiting_auth` 转移中携带；
- `waiting_user` 与 `waiting_auth` 语义严格分离，不允许复用。
- `waiting_auth` 不能被客户端解释为“当前一定是 interactive”；它只说明 run 已进入 auth contract。
- 当前 UI 状态必须来自 `.state/state.json` + FCMP 增量，不得从 `result/result.json` 反推。
- `resume_cause` / `pending_owner` / `resume_ticket_id` / `ticket_consumed` 为可选扩展字段，用于描述 waiting 态离开时的 winner 路径；
- `meta.attempt` 表示该事件归属的已 materialize attempt，而不是未来 attempt 的预约值。
- terminal lifecycle 统一折叠进 `data.terminal`，不再额外发送 `conversation.completed` 或 `conversation.failed`。

terminal 示例：

```json
{
  "type": "conversation.state.changed",
  "data": {
    "from": "running",
    "to": "failed",
    "trigger": "turn.failed",
    "updated_at": "2026-02-24T12:34:56.000000",
    "pending_interaction_id": null,
    "pending_auth_session_id": null,
    "terminal": {
      "status": "failed",
      "reason_code": "NON_ZERO_EXIT",
      "error": {
        "category": "runtime",
        "code": "NON_ZERO_EXIT",
        "message": "process exited with non-zero status"
      },
      "diagnostics": []
    }
  }
}
```

### 3.2 `interaction.reply.accepted`

```json
{
  "type": "interaction.reply.accepted",
  "data": {
    "interaction_id": 7,
    "resolution_mode": "user_reply",
    "accepted_at": "2026-02-24T12:35:10.000000",
    "response_preview": "用户回复文本摘要"
  }
}
```

说明：

- canonical 发布路径为：`POST /interaction/reply` -> orchestrator `interaction.reply.accepted` -> FCMP `interaction.reply.accepted`。
- `user.input.required.data.prompt` 保留为语义化提示文本；
- 不应写入无意义占位值（例如 `"Provide next user turn"`）。
- `interaction_id` 为 attempt-scoped identity；消费或对账时必须结合来源 attempt 解释。
- `user.input.required` 才是 user-reply contract 的证据；客户端不应仅凭状态名推断是否允许回复。

### 3.3 `interaction.auto_decide.timeout`

```json
{
  "type": "interaction.auto_decide.timeout",
  "data": {
    "interaction_id": 7,
    "resolution_mode": "auto_decide_timeout",
    "timeout_sec": 1200,
    "policy": "engine_judgement",
    "accepted_at": "2026-02-24T12:55:10.000000"
  }
}
```

### 3.4 `auth.required`

```json
{
  "type": "auth.required",
  "data": {
    "auth_session_id": "auth-session-123",
    "engine": "opencode",
    "provider_id": "google",
    "challenge_kind": "api_key",
    "prompt": "Authentication is required to continue.",
    "auth_url": null,
    "user_code": null,
    "instructions": "Paste an API key in the chat input to continue.",
    "accepts_chat_input": true,
    "input_kind": "api_key",
    "last_error": null,
    "source_attempt": 1
  }
}
```

说明：

- `auth.required` 只说明进入 auth contract，不说明 `execution_mode`。
- 如果客户端要判断是否具备真实会话能力，必须读取 status/read-model 中的 `conversation_mode`，不能从 FCMP 状态名反推。
- 对于新 run，current waiting payload 只存在于 `.state/state.json.pending`，不再存在独立 `pending_auth*.json`。
- 多方式鉴权下，`auth.required(phase=method_selection)` 才表示客户端需要先选择鉴权方式。
- 单方式鉴权下，可直接暴露 `challenge_active`，不需要 method selection。

### 3.5 `auth.challenge.updated`

```json
{
  "type": "auth.challenge.updated",
  "data": {
    "auth_session_id": "auth-session-123",
    "engine": "opencode",
    "provider_id": "google",
    "challenge_kind": "api_key",
    "prompt": "Authentication is still required.",
    "auth_url": null,
    "user_code": null,
    "instructions": "The submitted API key was rejected. Paste a new key to retry.",
    "accepts_chat_input": true,
    "input_kind": "api_key",
    "last_error": "API key rejected",
    "source_attempt": 1
  }
}
```

说明：

- `auth.challenge.updated` 只表示 challenge-active 内的真实 challenge 更新或重投影。
- `auth.session.busy` 不得被转译成新的 challenge，也不得伪装成 method-selection 事件。

### 3.6 `auth.input.accepted`

```json
{
  "type": "auth.input.accepted",
  "data": {
    "auth_session_id": "auth-session-123",
    "submission_kind": "api_key",
    "accepted_at": "2026-02-24T12:35:10.000000"
  }
}
```

### 3.7 `auth.completed`

```json
{
  "type": "auth.completed",
  "data": {
    "auth_session_id": "auth-session-123",
    "completed_at": "2026-02-24T12:35:20.000000",
    "resumed_from_attempt": 1,
    "resume_attempt": 2,
    "source_attempt": 1,
    "target_attempt": 2,
    "resume_ticket_id": "ticket-123",
    "ticket_consumed": true
  }
}
```

说明：

- `resume_attempt` / `target_attempt` 表示将要进入的目标 attempt；
- `auth.completed` 事件本身不表示该目标 attempt 已经 started；
- 真正的新执行开始仍由后续 `conversation.state.changed(queued->running)` 表示。
- 如果 queued resume 在 redrive 前发现 run folder 已缺失，系统会直接收敛到 terminal failed；
- 此时不会 materialize 新 attempt，`attempt audit missing` 只能说明未启动，不应被解释为“attempt 3 已开始”。

### 3.8 `auth.failed`

```json
{
  "type": "auth.failed",
  "data": {
    "auth_session_id": "auth-session-123",
    "failed_at": "2026-02-24T12:35:20.000000",
    "message": "Authentication session can no longer continue."
  }
}
```

## 4. SSE Contract

`GET /v1/jobs/{request_id}/events?cursor=...`

`GET /v1/management/runs/{request_id}/events?cursor=...`

事件类型：

- `snapshot`：首帧快照（`status`, `cursor`, `pending_interaction_id?`, `pending_auth_session_id?`）
- `chat_event`：FCMP 业务事件
- `heartbeat`：传输层保活

## 5. State / Audit Read Priority

对于新 run，读取优先级固定为：

1. `.state/state.json`
2. `.state/dispatch.json`
3. `.audit/*`
4. `result/result.json`

说明：

- `.audit/request_input.json` 是唯一 request 输入快照文件。
- `.audit/parser_diagnostics.*.jsonl` 只提供诊断信息，不具备当前状态权威。
- `status.json`、`current/projection.json`、`raw/output.json`、`logs/stdout.txt`、`logs/stderr.txt` 都属于 legacy 文件，不再参与 canonical 读路径。

## 5. Current Truth vs History Truth

本协议明确区分：

- `.state/state.json`
  当前状态权威
- `.state/dispatch.json`
  dispatch 生命周期权威
- `.audit/*`
  历史事件与审计事实
- `result/result.json`
  terminal-only

因此：

- FCMP 是 history/event truth，不是 current-state file
- UI 当前状态必须优先读取 `.state/state.json`
- parser diagnostics 只能作为 diagnostics，不得被解释为 terminal failure
- `result/result.json` 不再代表 waiting/running/queued snapshot

说明：

- 不再对外发送 `run_event/status/stdout/stderr/end`。
- `heartbeat` 为传输层事件，不属于 FCMP 业务模型。

## 5. Cursor & History

- `cursor`：基于 `chat_event.seq`（跨 attempt 全局 FCMP seq）。
- `GET /v1/jobs/{request_id}/events/history` 返回 FCMP 历史。
- `GET /v1/management/runs/{request_id}/events/history` 返回 FCMP 历史。
- `GET /v1/jobs/{request_id}/result` 仅表示 terminal result，不再表示 waiting/current snapshot。

约束：

- `seq` 在同一 run 内跨 attempt 全局连续递增；
- attempt 内局部序号通过 `meta.local_seq` 保留；
- 续跑 attempt 中 `interaction.reply.accepted` 先于该轮 `assistant.message.final`。
- `conversation.state.changed(waiting_* -> queued)` 先于对应 target attempt 的 `queued -> running`；
- 同一个 `resume_ticket_id` 只允许驱动一个 target attempt started。

## 6. Raw Evidence Jump

FCMP `raw_ref` 可回跳日志字节区间：

- `GET /v1/jobs/{request_id}/logs/range?stream=stdout&byte_from=...&byte_to=...`
- `GET /v1/management/runs/{request_id}/logs/range?...`

## 7. Audit Files

`data/runs/<run_id>/.audit/`（按 attempt 分片）：

- `events.{attempt}.jsonl`（RASP 审计）
- `fcmp_events.{attempt}.jsonl`（FCMP 对外事件，`seq` 全局，`meta.local_seq` 本地）
- `parser_diagnostics.{attempt}.jsonl`
- `protocol_metrics.{attempt}.json`
- `orchestrator_events.{attempt}.jsonl`（编排事件事实）

## 7.1 Live Publish Truth Hierarchy

活跃 run 的协议真相链路现在是：

1. adapter chunk 输出
2. live parser session 增量解析
3. FCMP / RASP publisher 分配 seq 并发布到 live journal
4. SSE / history 优先从 live journal 读取
5. audit mirror 异步追加到 `.audit/*.jsonl`

因此：

- `.audit/fcmp_events.*.jsonl` 不再是活跃 SSE 的前置条件
- 活跃与近期 run 的 `/events/history` 先读内存，再按需回退到 audit
- RASP 顺序由 live parser emission 顺序定义，而不是由 audit 文件 mtime 定义

## 8. Statechart Alignment

会话状态机 SSOT：`docs/session_runtime_statechart_ssot.md`

FCMP 关键对齐：

- `turn.started` / `turn.needs_input` / `turn.succeeded` / `turn.failed` / `run.canceled`
  -> `conversation.state.changed`
- `auth.required` / `auth.completed` / `auth.failed`
  -> `conversation.state.changed`
- `interaction.reply.accepted`
  -> `conversation.state.changed(waiting_user -> queued)`
- `interaction.auto_decide.timeout`
  -> `conversation.state.changed(waiting_user -> queued)`
- `auth.completed`
  -> `conversation.state.changed(waiting_auth -> queued)`
  仅允许来自 canonical auth completion；不得由 readiness-like signal 推断生成

`auto` 继续作为 `interactive` 子集策略，共享同一状态机与终态映射。

## 9. Schema Contract

协议 Schema SSOT：

- `server/assets/schemas/protocol/runtime_contract.schema.json`

核心 `$defs`：

- `fcmp_event_envelope`
- `rasp_event_envelope`
- `orchestrator_event`
- `pending_interaction`
- `pending_auth`
- `interaction_history_entry`
- `interactive_resume_command`

校验策略：

- 写入路径（SSE 输出/审计落盘/交互存储）为硬校验；
- 读取路径（history/旧审计）为兼容过滤；
- 内部桥接失败记录 `diagnostic.warning(code=SCHEMA_INTERNAL_INVALID)`。

错误码：

- `PROTOCOL_SCHEMA_VIOLATION`
