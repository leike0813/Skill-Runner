## 1. OpenSpec artifacts

- [x] 1.1 创建 `introduce-in-conversation-auth-flow` change
- [x] 1.2 补齐 proposal / design / tasks
- [x] 1.3 编写新 capability spec：`in-conversation-auth-flow`
- [x] 1.4 编写 delta specs：`session-runtime-statechart-ssot`、`engine-execution-failfast`、`interactive-run-lifecycle`、`engine-adapter-runtime-contract`

## 2. SSOT and protocol

- [x] 2.1 在 `docs/contracts/session_fcmp_invariants.yaml`、`docs/session_runtime_statechart_ssot.md`、`server/runtime/session/statechart.py` 中新增 `waiting_auth` 与相关状态迁移
- [x] 2.2 在 `server/assets/schemas/protocol/runtime_contract.schema.json`、`server/models/runtime_event.py`、`server/runtime/protocol/event_protocol.py`、`server/runtime/protocol/factories.py` 中新增 auth 事件族和 payload schema
- [x] 2.3 在 `docs/runtime_event_schema_contract.md`、`docs/session_event_flow_sequence_fcmp.md`、`docs/runtime_stream_protocol.md` 中同步新的 FCMP/RASP ordering 与 auth 事件语义

## 3. Models and persistence

- [x] 3.1 在 `server/models/common.py` 中新增 `RunStatus.WAITING_AUTH`
- [x] 3.2 在 `server/models/interaction.py` 中新增 `PendingAuth` / `AuthReplyRequest` 等模型，并把 reply 请求扩展为 union
- [x] 3.3 在 `server/services/orchestration/run_store.py` 中新增 `pending_auth`、`auth_resume_context` 等持久化字段与读写方法
- [x] 3.4 在 `server/services/orchestration/run_audit_service.py` 中新增 `auth_session` attempt 审计结构与 redacted submission 记录

## 4. Orchestration and auth flow integration

- [x] 4.1 新增 `server/services/orchestration/run_auth_orchestration_service.py`，实现 run <-> auth session 绑定、输入提交、callback 完成与恢复调度
- [x] 4.2 在 `server/services/orchestration/run_job_lifecycle_service.py` 中把高置信度会话型 `auth_detection` 改为进入 `waiting_auth`
- [x] 4.3 在 `server/services/orchestration/run_interaction_service.py` 中扩展 pending 查询和 reply 提交，支持 `mode=auth`
- [x] 4.4 在 `server/routers/oauth_callback.py` 与 `server/services/engine_management/engine_auth_flow_manager.py` 中接入 run-scoped auth 完成通知

## 5. Client and observability

- [x] 5.1 在 `server/runtime/observability/run_observability.py` 中暴露 `pending_auth`、auth 事件与 attempt-level auth session 数据
- [x] 5.2 在 `e2e_client/templates/run_observe.html` 中新增 auth card、聊天输入模式切换与 redacted 提交占位
- [x] 5.3 确保 raw authorization code / API key 不进入 FCMP history、SSE、`.audit/meta`、parser diagnostics 和消息历史

## 6. Verification

- [x] 6.1 新增 auth 相关 unit / integration tests
- [x] 6.2 运行 runtime 必跑清单及新增 auth 测试
- [x] 6.3 运行必要的 cursor/history / dedup 回归测试
- [x] 6.4 运行 mypy
