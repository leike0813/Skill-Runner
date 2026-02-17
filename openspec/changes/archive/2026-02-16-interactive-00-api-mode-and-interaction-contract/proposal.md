## Why

当前 `/v1/jobs` 仅支持“一次提交、全自动执行、终态返回”的流程。  
要支持“执行中让 Agent 请求用户决策/补充信息，再继续执行”，必须先定义稳定的 API 合同，否则后续编排与适配层无法一致实现。

此外，本轮决策已明确：
1. 交互模式先只走 API（不做 UI 交互入口）。
2. 后续 `waiting_user` 生命周期将释放并发槽位（由下游 change 细化）。

## What Changes

1. 新增任务执行模式字段（保持默认兼容）：
   - 在运行参数中引入 `execution_mode`，枚举：`auto | interactive`。
   - 默认值为 `auto`，不影响现有调用方。

2. 新增交互 API（仅 API 路径）：
   - `GET /v1/jobs/{request_id}/interaction/pending`
   - `POST /v1/jobs/{request_id}/interaction/reply`

3. 定义交互请求/响应契约：
   - `pending` 结构（问题文本、可选项、字段约束、交互 id、上下文摘要）。
   - `reply` 结构（目标 interaction_id、用户答复、可选 idempotency key）。

4. 定义状态前置条件与错误语义：
   - 仅 `waiting_user` 状态接受 `reply`。
   - 交互 id 过期/不匹配返回冲突错误（409）。
   - 对非交互模式请求交互端点返回明确错误（400/409）。

5. 定义缓存边界：
   - `interactive` 模式默认不走缓存命中与回填，避免把“人类决策差异”错误去重。

## Impact

- `server/models.py`
- `server/services/options_policy.py`
- `server/assets/configs/options_policy.json`
- `server/routers/jobs.py`
- `server/services/run_store.py`（为后续状态与交互持久化扩展预留字段）
- `docs/api_reference.md`
- `tests/unit/test_v1_routes.py`
- `tests/unit/test_runs_router_cache.py`
