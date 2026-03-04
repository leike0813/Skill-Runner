## Context

FCMP 是 runtime 协议流，不是聊天窗口的专用真相源。当前聊天窗口把 FCMP、前端乐观插入和 history 回放混用，导致刷新后聊天窗口与 live 阶段不一致。

本 change 引入独立的 canonical chat replay：

- live source: `ChatReplayLiveJournal`
- persisted source: `.audit/chat_replay.jsonl`
- publish: `ChatReplayPublisher`
- consumption: `/chat` SSE 与 `/chat/history`

FCMP 继续用于 runtime observability，不承担聊天气泡真相源职责。

## Goals / Non-Goals

**Goals**
- 为聊天气泡建立 run-scoped 全局顺序的后端 SSOT。
- 统一用户端与管理端聊天窗口的数据来源。
- 让 refresh / reconnect 与 live 展示完全一致。
- 禁止前端本地乐观插入聊天气泡。

**Non-Goals**
- 不替代 FCMP 作为 runtime 协议流。
- 不把 pending cards 本身转换成聊天气泡。
- 不修改 `.state/state.json` 的状态真相地位。

## Decisions

### 1. Chat replay 独立于 FCMP

- canonical chat replay 使用独立 schema 与 journal
- `/chat` 与 `/chat/history` 只返回 chat replay 事件
- `/events` 与 `/events/history` 继续保留给 protocol/observability

### 2. run-scoped global ordering

- `chat_seq` 在 run 级别单调递增
- persisted truth 为 `.audit/chat_replay.jsonl`
- 前端不得自行重排

### 3. 三种角色

- `user`
- `assistant`
- `system`

非模型生成的编排提示统一为 `system`，不再伪装成 `assistant`。

### 4. 来源规则

- `interaction.reply.accepted` -> `user` / `interaction_reply`
- `auth.input.accepted` -> `user` / `auth_submission`
- `assistant.message.final` -> `assistant` / `assistant_final`
- `auth.completed`、`auth.failed`、timeout、terminal summary -> `system` / `orchestration_notice`

### 5. 前端禁止乐观插入

- reply / auth submit 后，前端只显示 pending 状态
- 聊天气泡只能来自 `/chat` 或 `/chat/history`

### 6. history 与 live 一致

- active/recent runs: memory-first replay
- fallback: `.audit/chat_replay.jsonl`
- 不再从 FCMP 反推聊天窗口

## Risks / Trade-offs

- 引入了额外的 shared runtime capability，需要同步 schema、router、frontend 和 observability。
- system 气泡与 pending card 分离后，前端需要同时维护两条显示通道，但职责更清晰，也更稳定。
