## 1. Protocol Refactor

- [ ] 1.1 `runtime_event_protocol` 新增 FCMP 事件：`conversation.state.changed`
- [ ] 1.2 `runtime_event_protocol` 新增 FCMP 事件：`interaction.reply.accepted`
- [ ] 1.3 `runtime_event_protocol` 新增 FCMP 事件：`interaction.auto_decide.timeout`
- [ ] 1.4 终态/等待态映射改为消费 canonical 状态事实（不依赖 RASP lifecycle 推断）

## 2. SSE / History Unification

- [ ] 2.1 `run_observability.iter_sse_events` 改为 chat-only 业务输出
- [ ] 2.2 `cursor` 切换到 FCMP `seq`
- [ ] 2.3 `/events/history` 切换到 `fcmp_events.jsonl`
- [ ] 2.4 管理端与 temp-skill-run 路由同步 query/契约变更

## 3. Client Updates

- [ ] 3.1 `run_detail.html` 移除 run_event/status/stdout/stderr/end 监听
- [ ] 3.2 `run_observe.html` 切换为 chat-only 消费与 FCMP cursor
- [ ] 3.3 e2e backend/routes 同步 stream 参数收敛

## 4. Docs

- [ ] 4.1 更新 `docs/runtime_stream_protocol.md` 为 FCMP 单流说明
- [ ] 4.2 新增 `docs/session_event_flow_sequence_fcmp.md`
- [ ] 4.3 更新 `docs/api_reference.md` 与 `docs/dev_guide.md` 的 SSE/history 描述

## 5. Tests

- [ ] 5.1 `test_runtime_event_protocol.py` 覆盖 3 个新增 FCMP 事件
- [ ] 5.2 `test_run_observability.py` 覆盖 chat-only SSE 与 FCMP cursor/history
- [ ] 5.3 `test_protocol_state_alignment.py` 覆盖 canonical transition 映射
- [ ] 5.4 更新受影响路由/UI 单测断言（移除旧 SSE 事件依赖）
