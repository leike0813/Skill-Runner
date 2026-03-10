# Change: gemini-iflow-handle-event-consumption-and-turn-complete-payload-unification

## Why
- Gemini 与 iFlow 尚未将 run handle 统一事件化，`waiting_user` 仍依赖旧提取路径，导致消费链路双轨。
- `agent.turn_complete` 目前仅空载荷，无法承载执行统计信息，影响审计可读性与后续前端增强。
- Codex 与 OpenCode 已有明确终态原始语义（`turn.completed` / `step_finish`），但未完整映射到 `agent.turn_complete.data`。

## What Changes
1. `agent.turn_complete.data` 改为直接承载结构化对象（不再套 `details`）。
2. Gemini parser:
   - `session_id` -> `lifecycle.run_handle.handle_id`
   - `stats` -> `agent.turn_complete.data`
   - 语义命中后抑制对应 raw（保留 raw_ref）
3. iFlow parser:
   - 块级解析 stdout/stderr（避免逐行）
   - `<Execution Info>` JSON 的 `session-id` -> run_handle
   - 其余字段 -> `agent.turn_complete.data`
   - 保留 channel 漂移纠偏与诊断告警
4. Codex/OpenCode 补齐 turn_complete 承载：
   - Codex `turn.completed.usage` -> `agent.turn_complete.data`
   - OpenCode `step_finish.part.cost/tokens` -> `agent.turn_complete.data.cost/tokens`
5. 生命周期硬切：
   - `run_handle` 只走 live 事件即时消费
   - `persist_waiting_interaction` 移除 `extract_session_handle` 逻辑
   - waiting_user 前无 handle 则失败 `SESSION_RESUME_FAILED`

## Scope
- 协议合同、解析器、live 发布、lifecycle 消费路径与相关测试。
- 无新增/删除 HTTP API。
- FCMP/chat 事件类型不变。
