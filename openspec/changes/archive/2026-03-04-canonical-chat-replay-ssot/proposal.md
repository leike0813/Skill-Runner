## Why

当前聊天窗口的真相源混杂在三处：

- FCMP 事件流
- 前端本地乐观插入
- history 刷新时对 interaction/auth 记录的隐式补拼

这导致了两个持续性问题：

- refresh 后用户回复或鉴权提交气泡丢失
- live 与 history 的聊天顺序漂移，尤其在鉴权恢复场景中表现为用户和系统消息反转

需要一个独立于 FCMP 的 canonical chat replay 通道，把聊天气泡统一收敛为后端 SSOT，并禁止前端自行拼接或乐观插入气泡。

## What Changes

- 新增独立的 canonical chat replay 模型、live journal、audit mirror 与 `/chat`、`/chat/history` 接口。
- 聊天气泡以 run-scoped `chat_seq` 全局递增顺序持久化到 `.audit/chat_replay.jsonl`。
- 用户端与管理端聊天窗口改为只消费 canonical chat replay，不再直接消费 FCMP。
- 用户回复、鉴权提交、助手最终回复、系统提示统一由后端派生并发布为 canonical chat replay 事件。
- 前端移除本地乐观聊天气泡插入逻辑。

## Capabilities

### New Capabilities

- `canonical-chat-replay`: 后端提供独立于 FCMP 的聊天气泡 live stream 与 history replay，作为聊天窗口唯一真相源。

### Modified Capabilities

- `interactive-job-api`: 用户端聊天窗口改为使用 `/chat` 与 `/chat/history`，不再从 FCMP 事件流直接渲染气泡。
- `job-orchestrator-modularization`: orchestrator/runtime 在写 reply、auth submit、assistant final、system notice 时，必须同步发布 canonical chat replay。

## Impact

- Affected code:
  - `server/runtime/chat_replay/*`
  - `server/runtime/observability/run_observability.py`
  - `server/runtime/observability/run_read_facade.py`
  - `server/routers/jobs.py`
  - `server/routers/temp_skill_runs.py`
  - `server/routers/management.py`
  - `server/assets/templates/ui/run_detail.html`
  - `e2e_client/templates/run_observe.html`
- Affected tests:
  - `tests/unit/test_e2e_run_observe_semantics.py`
  - `tests/unit/test_ui_routes.py`
  - `tests/unit/test_v1_routes.py`
  - `tests/unit/test_management_routes.py`
  - new `tests/unit/test_chat_replay_*`
- Public API impact:
  - 新增 `/chat` 与 `/chat/history`
  - 现有 `/events` 与 `/events/history` 保留，但从聊天窗口退役
