## Why

当前 runtime 在 streamed RASP、parser-originated FCMP、orchestration-originated FCMP、history replay、audit mirror 和 terminal/result projection 之间缺少统一的顺序与因果合同。结果是活跃 run 的会话语义、状态投影、结果投影和历史回放可能出现顺序漂移，触发 `waiting_user` 仍在却先看到空 terminal result、鉴权提示顺序反转、live/history 顺序不一致等问题。

除了顺序缺失之外，FCMP 还保留了一套冗余的 conversation lifecycle 事件：`conversation.started`、`conversation.completed`、`conversation.failed` 与 `conversation.state.changed` 在生命周期表达上重复，进一步增加了 paired-event 规则、UI 渲染分支和终态时序复杂度。现在必须先把顺序合同和 lifecycle 事件收敛一起 formalize，再允许后续 live-stream 实现继续推进。

## What Changes

- 新增一个专门的 runtime event ordering capability，用于定义 streamed RASP、parser-originated FCMP、orchestration-originated FCMP、history replay、audit mirror 和 terminal/result projection 的职责边界与保序合同。
- 新增独立的机器可读合同文件 `docs/contracts/runtime_event_ordering_contract.yaml`，定义顺序域、前置规则、发布 gating、projection gating、replay consistency 和缓冲策略。
- 为 active runtime event 明确 canonical order source：发布顺序决定活跃顺序，audit mirror 和 batch backfill 只能镜像或补历史，不能重定义顺序。
- 引入顺序仲裁层设计骨架：parser、orchestration、projection 先产出 candidate，再由 gate/buffer 判定是否可发布。
- 收敛 FCMP conversation lifecycle 事件模型：删除 `conversation.started`、`conversation.completed`、`conversation.failed`，仅保留 `conversation.state.changed` 作为唯一 lifecycle 事件。
- 将 terminal 语义统一折叠进 `conversation.state.changed.data.terminal`，包括 terminal status、error 和 diagnostics。
- 为 auth、waiting/reply、terminal/result projection 补充强制性的因果先后约束，禁止投影超前于源事件。
- 为 live SSE 与 `/events/history` 补充一致性要求，要求 replay 必须保持 canonical publish order。
- 将 batch rebuild 明确降级为 parity/backfill only，禁止覆盖已经发布过的 live order。

## Capabilities

### New Capabilities
- `runtime-event-ordering-contract`: 定义 streamed RASP、FCMP、history replay、audit mirror、projection gating、buffering policy 和 lifecycle normalization 的统一顺序与因果合同。

### Modified Capabilities
- `interactive-job-api`: 补充 live SSE、history replay、auth 引导和 terminal projection 的顺序约束，并要求对外仅暴露 canonical lifecycle FCMP。
- `job-orchestrator-modularization`: 补充 orchestration-originated lifecycle FCMP 的统一发布边界，以及 result projection 的 gating 约束。
- `engine-adapter-runtime-contract`: 补充 live parser emission 顺序、RASP 顺序定义、candidate 生成边界和 parser-originated FCMP 的来源约束。

## Impact

- 受影响的协议与 SSOT：
  - `docs/contracts/session_fcmp_invariants.yaml`
  - `docs/contracts/runtime_event_ordering_contract.yaml`
  - `docs/runtime_stream_protocol.md`
  - `docs/runtime_event_schema_contract.md`
  - `docs/session_event_flow_sequence_fcmp.md`
- 受影响的主 specs：
  - `interactive-job-api`
  - `job-orchestrator-modularization`
  - `engine-adapter-runtime-contract`
  - 新增 `runtime-event-ordering-contract`
- 预期后续实现影响面：
  - `server/runtime/protocol/live_publish.py`
  - `server/runtime/protocol/event_protocol.py`
  - `server/runtime/protocol/factories.py`
  - `server/runtime/protocol/contracts.py`
  - `server/runtime/observability/run_observability.py`
  - `server/runtime/observability/run_read_facade.py`
  - `server/runtime/adapter/base_execution_adapter.py`
  - 各 engine stream parser
  - `server/services/orchestration/*` 中发布 lifecycle FCMP 与 result projection 的路径
  - FCMP 对外 schema、UI 消费逻辑和相关测试
