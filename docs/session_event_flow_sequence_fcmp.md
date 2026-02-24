# Session Event Flow (FCMP Single-Stream SSOT)

本文档给出 FCMP 单流后的端到端事件时序图，作为 `docs/session_runtime_statechart_ssot.md` 的事件流视角补充。

## 1) 主执行流（queued -> running -> terminal）

不变量锚点：`TR-01`、`TR-05`、`TR-06`、`TR-09`、`FM-01`、`FM-05`、`FM-06`、`FM-07`、`OR-01`。

```mermaid
sequenceDiagram
    participant C as Client(UI)
    participant API as SSE API
    participant O as Orchestrator
    participant P as Protocol(FCMP)

    C->>API: GET /events?cursor=n
    API-->>C: snapshot(status=queued|running)
    O->>P: turn.started
    P-->>API: chat_event(conversation.state.changed queued->running)
    API-->>C: chat_event
    O->>P: assistant output parsed
    P-->>API: chat_event(assistant.message.final)
    API-->>C: chat_event
    alt completed
      O->>P: turn.succeeded
      P-->>API: chat_event(conversation.state.changed running->succeeded)
      P-->>API: chat_event(conversation.completed)
    else failed/canceled
      O->>P: turn.failed | run.canceled
      P-->>API: chat_event(conversation.state.changed running->failed|canceled)
      P-->>API: chat_event(conversation.failed)
    end
    API-->>C: chat_event(...)
```

## 2) 交互回复流（waiting_user -> queued -> running）

不变量锚点：`TR-02`、`TR-03`、`FM-02`、`FM-03`、`PE-01`、`OR-02`、`OR-04`。

```mermaid
sequenceDiagram
    participant C as Client(UI)
    participant API as Jobs API
    participant O as Orchestrator
    participant P as Protocol(FCMP)

    O->>P: turn.needs_input
    P-->>C: chat_event(conversation.state.changed running->waiting_user)
    P-->>C: chat_event(user.input.required)

    C->>API: POST /interaction/reply
    API->>O: interaction.reply.accepted
    O->>P: interaction.reply.accepted
    P-->>C: chat_event(interaction.reply.accepted)
    P-->>C: chat_event(conversation.state.changed waiting_user->queued)

    O->>P: turn.started
    P-->>C: chat_event(conversation.state.changed queued->running)
    O->>P: assistant output parsed
    P-->>C: chat_event(assistant.message.final)
```

## 3) strict=false 超时自动决策流

不变量锚点：`TR-02`、`TR-04`、`FM-02`、`FM-04`、`PE-02`、`OR-02`。

```mermaid
sequenceDiagram
    participant Timer as Timeout Watcher
    participant O as Orchestrator
    participant P as Protocol(FCMP)
    participant C as Client(UI)

    O->>P: turn.needs_input
    P-->>C: chat_event(conversation.state.changed running->waiting_user)
    P-->>C: chat_event(user.input.required)

    Timer->>O: waiting reached session_timeout_sec
    O->>P: interaction.auto_decide.timeout
    P-->>C: chat_event(interaction.auto_decide.timeout)
    P-->>C: chat_event(conversation.state.changed waiting_user->queued)

    O->>P: turn.started
    P-->>C: chat_event(conversation.state.changed queued->running)
```

## 4) 重启恢复流（preserve / reconcile）

不变量锚点：`TR-10`、`TR-11`、`TR-12`、`TR-13`。

```mermaid
sequenceDiagram
    participant Boot as Orchestrator Startup
    participant Store as Runtime Store
    participant P as Protocol(FCMP)
    participant C as Client(UI)

    Boot->>Store: read pending + session handle
    alt pending/handle valid
      Boot->>P: restart.preserve_waiting
      P-->>C: chat_event(conversation.state.changed running->waiting_user)
      P-->>C: chat_event(user.input.required)
    else invalid
      Boot->>P: restart.reconcile_failed
      P-->>C: chat_event(conversation.state.changed running->failed)
      P-->>C: chat_event(conversation.failed error=SESSION_RESUME_FAILED)
    end
```

## 5) Statechart 映射说明

不变量锚点：`FM-01` ~ `FM-07`、`PE-01`、`PE-02`、`OR-03`、`OR-04`。

- `turn.started` -> `conversation.state.changed(... to=running)`
- `turn.needs_input` -> `conversation.state.changed(... to=waiting_user)` + `user.input.required`
- `interaction.reply.accepted` -> `interaction.reply.accepted` + `conversation.state.changed(waiting_user->queued)`
- `interaction.auto_decide.timeout` -> `interaction.auto_decide.timeout` + `conversation.state.changed(waiting_user->queued)`
- `turn.succeeded` -> `conversation.state.changed(... to=succeeded)` + `conversation.completed`
- `turn.failed` / `run.canceled` -> `conversation.state.changed(... to=failed|canceled)` + `conversation.failed`
