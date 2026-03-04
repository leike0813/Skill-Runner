## Why

当前高置信度 `auth_detection` 在后台 run 中只能把任务直接归为 `AUTH_REQUIRED` 失败。对于承接 FCMP 的会话型客户端，这个行为过于粗糙：用户已经在聊天窗口里，却必须跳出会话去手工完成鉴权，再重新发起任务，既破坏了连续对话体验，也让编排器无法在同一 `run_id`、同一环境下恢复执行。

同时，这个特性不是单点 UI 改动，而是一次 runtime SSOT 级别的重构。它要求 canonical statechart、FCMP/RASP 合同、runtime schema、parser/translator、observability、run store 和 orchestrator 全部对 `waiting_auth` 及其恢复语义达成一致。如果没有先把这些 SSOT 和实现层一起设计清楚，后续容易在 `waiting_user`、`AUTH_REQUIRED` 和新 auth 子流程之间发生语义漂移。

## What Changes

- 在 canonical statechart 中新增可恢复状态 `waiting_auth`，用于承接会话内鉴权。
- 将会话型 run 中的高置信度 `auth_detection` 从“直接失败”改为“创建 auth session 并进入 `waiting_auth`”。
- 复用 `engine_auth_flow_manager` 作为 engine 级鉴权子编排器，并新增 run-scoped 绑定服务，把 `run_id / attempt / engine / provider_id / workspace context` 与 auth session 绑定。
- 扩展 FCMP/RASP 事件族，新增 `auth.required / auth.challenge.updated / auth.input.accepted / auth.completed / auth.failed`。
- 复用现有聊天输入提交路径，让用户能在聊天窗口内提交 authorization code 或 API Key；同时要求 raw secret 不进入消息历史、事件 payload、审计日志。
- 在鉴权成功后，以同一 `run_id`、同一环境、新 `attempt` 的方式恢复执行。

## Capabilities

### New Capabilities
- `in-conversation-auth-flow`: 定义会话内鉴权的 canonical 状态、事件、输入提交、恢复执行与安全约束。

### Modified Capabilities
- `session-runtime-statechart-ssot`: 增加 `waiting_auth` canonical state 与相关状态迁移、恢复约束。
- `engine-execution-failfast`: 将高置信度 `auth_detection` 在会话型 run 中从“直接 `AUTH_REQUIRED` 失败”改为“进入 `waiting_auth`”，同时保留 headless/非会话兼容行为。
- `interactive-run-lifecycle`: 在 `waiting_user` 之外新增 `waiting_auth` 子流程，并明确高置信度鉴权命中的优先级和恢复路径。
- `engine-adapter-runtime-contract`: 明确 adapter/runtime 必须持续暴露可供 auth detection 与 auth challenge 构造消费的证据材料。

## Impact

- 主要影响 `server/runtime/session/*`、`server/runtime/protocol/*`、`server/runtime/observability/*`、`server/services/orchestration/*`、`server/services/engine_management/*`、`server/models/*` 与 `e2e_client/templates/*`。
- 需要同步更新 `docs/contracts/session_fcmp_invariants.yaml`、runtime schema、相关文档和 runtime 必跑测试。
- 不新增新的 HTTP callback 路径，不引入新的外部依赖。
- 对外 HTTP API 只在现有聊天回复提交路径上扩展 union 请求体；非会话 / headless run 的默认行为保持兼容。
