## Why

`interactive-44` 已完成 session 状态机收敛，但运行时事件流仍保留双轨消费语义（`run_event` + `chat_event`），且 SSE 存在 `status/stdout/stderr/end` 侧带依赖，导致：

- 客户端消费面复杂且冗余；
- cursor/history 语义分裂（RASP seq 与 FCMP seq）；
- 状态机事件与协议事件映射不够直接。

需要新增独立变更，将事件架构收敛为 FCMP 单流并补充最小事件集，形成可追溯闭环。

## Dependencies

- 依赖 `interactive-44-single-resumable-session-statechart-ssot` 的单可恢复状态机决策。
- 不改动 `interactive-44` 的核心语义，只在事件协议与观测层追加收敛。

## What Changes

1. SSE 对外业务事件收敛为 `chat_event`（FCMP）；`run_event/status/stdout/stderr/end` 退出对外业务契约。
2. FCMP 新增事件类型：
- `conversation.state.changed`
- `interaction.reply.accepted`
- `interaction.auto_decide.timeout`
3. `cursor` 与 `/events/history` 全面切换到 FCMP `seq`。
4. RASP 保留为审计内核（`events.jsonl`），不再作为客户端消费协议。
5. 新增 Sequence Diagram 文档，建立“Statechart 事件 -> FCMP 事件”映射 SSOT。

## Capabilities

### Modified
- `interactive-log-sse-api`
- `interactive-job-api`
- `session-runtime-statechart-ssot`

### Added
- `fcmp-event-model`
- `fcmp-cursor-history`

## Impact

- 代码：`server/services/runtime_event_protocol.py`, `server/services/run_observability.py`, `server/routers/*`, `server/assets/templates/ui/run_detail.html`, `e2e_client/templates/run_observe.html`
- 文档：`docs/runtime_stream_protocol.md`, `docs/session_event_flow_sequence_fcmp.md`, `docs/api_reference.md`, `docs/dev_guide.md`
