# Design

## Scope

本次只修复后端热路径：

- 修改 `server/runtime/observability/run_observability.py`
- 新增运行中 current attempt 的 FCMP / RASP live-only fast path
- 不改 UI 轮询逻辑
- 不改 `/chat`、`/chat/history`、`/events` SSE 逻辑

## Fast Path Rule

仅当以下条件同时成立时进入 fast path：

- `stream in {"fcmp", "rasp"}`
- run 状态属于活跃执行态：`queued` 或 `running`
- 请求的 attempt 解析结果等于当前 attempt

进入 fast path 后：

- 直接调用 `_get_live_protocol_payload(...)`
- 仅对 live rows 应用现有 filter / limit 逻辑
- 返回 `source="live"`
- 不读取 audit JSONL
- 不执行 `reindex_fcmp_global_seq(run_dir)`

## Guardrails

以下场景继续走现有 audit 路径：

- terminal run
- `waiting_user` / `waiting_auth` 等非活跃流式状态
- 显式请求旧 attempt
- `stream="orchestrator"`

这样可以避免影响现有 waiting 状态下的 chat / protocol 展示逻辑，也不改变 terminal 收尾与回放语义。

## Compatibility

- `protocol/history` 返回结构不变
- `events`、`cursor_floor`、`cursor_ceiling`、`attempt`、`available_attempts` 字段不变
- UI 无需改动
