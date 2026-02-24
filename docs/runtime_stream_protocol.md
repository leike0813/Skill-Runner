# Runtime Stream Protocol (FCMP Single-Stream)

## 1. Overview

Skill Runner 对外运行时事件流收敛为 FCMP 单流：

- `FCMP/1.0`：客户端唯一业务消费协议（SSE `event=chat_event`）。
- `RASP/1.0`：仅用于后端审计与证据保留，不作为客户端消费契约。

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
    "attempt": 2
  },
  "raw_ref": null
}
```

## 3. FCMP Event Types

- `conversation.started`
- `conversation.state.changed`
- `assistant.message.final`
- `user.input.required`
- `interaction.reply.accepted`
- `interaction.auto_decide.timeout`
- `conversation.completed`
- `conversation.failed`
- `diagnostic.warning`
- `raw.stdout` / `raw.stderr`

### 3.1 `conversation.state.changed`

```json
{
  "type": "conversation.state.changed",
  "data": {
    "from": "running",
    "to": "waiting_user",
    "trigger": "turn.needs_input",
    "updated_at": "2026-02-24T12:34:56.000000",
    "pending_interaction_id": 7
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
    "accepted_at": "2026-02-24T12:35:10.000000"
  }
}
```

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

## 4. SSE Contract

`GET /v1/jobs/{request_id}/events?cursor=...`

`GET /v1/management/runs/{request_id}/events?cursor=...`

事件类型：

- `snapshot`：首帧快照（`status`, `cursor`, `pending_interaction_id?`）
- `chat_event`：FCMP 业务事件
- `heartbeat`：传输层保活

说明：

- 不再对外发送 `run_event/status/stdout/stderr/end`。
- `heartbeat` 为传输层事件，不属于 FCMP 业务模型。

## 5. Cursor & History

- `cursor`：基于 `chat_event.seq`（FCMP seq）。
- `GET /v1/jobs/{request_id}/events/history` 返回 FCMP 历史。
- `GET /v1/management/runs/{request_id}/events/history` 返回 FCMP 历史。

## 6. Raw Evidence Jump

FCMP `raw_ref` 可回跳日志字节区间：

- `GET /v1/jobs/{request_id}/logs/range?stream=stdout&byte_from=...&byte_to=...`
- `GET /v1/management/runs/{request_id}/logs/range?...`

## 7. Audit Files

`data/runs/<run_id>/.audit/`：

- `events.jsonl`（RASP 审计）
- `fcmp_events.jsonl`（FCMP 对外事件）
- `parser_diagnostics.jsonl`
- `protocol_metrics.json`
- `orchestrator_events.jsonl`（编排事件事实）

## 8. Statechart Alignment

会话状态机 SSOT：`docs/session_runtime_statechart_ssot.md`

FCMP 关键对齐：

- `turn.started` / `turn.needs_input` / `turn.succeeded` / `turn.failed` / `run.canceled`
  -> `conversation.state.changed`
- `interaction.reply.accepted`
  -> `conversation.state.changed(waiting_user -> queued)`
- `interaction.auto_decide.timeout`
  -> `conversation.state.changed(waiting_user -> queued)`

`auto` 继续作为 `interactive` 子集策略，共享同一状态机与终态映射。
