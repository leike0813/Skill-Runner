## Why

最近几轮改动后，内建 E2E 客户端已经具备以下基线能力：
- source-aware 双链路映射（installed→`/v1/jobs/*`，temp→`/v1/temp-skill-runs/*`）
- `events/history` 与 `logs/range` 代理
- fixture skill 动态打包并走临时 skill 执行链路

但该 change 原始目标中的核心观测增强仍未完成（`raw_ref` 回跳、事件关联视图、低置信度提示、协议定位摘要录制）。  
若不先做边界收敛，后续实现与验收会出现“已完成能力重复实现”和“剩余增量不清晰”的问题。

## What Changes

- 收敛 change 边界：以“剩余增量”为主，不重复实现已落地基线能力。
- 升级 E2E 客户端 Run 观测页，补齐未落地的协议交互能力：
  - `run_event/chat_event` 的 FCMP-first 展示保持不变；
  - 新增 `raw_ref` 回跳预览（调用日志区间读取 API）；
  - 新增结构化事件关联视图（基于 `seq/correlation`）；
  - 新增低置信度可视标识（基于 `source.confidence`）。
- 升级 E2E 客户端录制能力：在保留当前轻量模型前提下，补充协议定位摘要字段并用于回放展示。
- 补齐观测增强对应测试（UI/代理/回放摘要）并更新文档与任务状态，确保 verify/archive 可追溯。
- 同步更新 `docs/e2e_example_client_ui_reference.md`，明确最新协议对齐后的页面能力与约束。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `builtin-e2e-example-client`: 扩展运行观测与回放能力以匹配最新协议（history/raw_ref/relation/low-confidence）。
- `builtin-e2e-example-client`: 增加 fixture temp-skill 动态打包执行能力（`tests/fixtures/skills` -> `/v1/temp-skill-runs`）。

## Impact

- Affected code:
  - `e2e_client/templates/run_observe.html`
  - `e2e_client/recording.py`
  - `e2e_client/templates/recording_detail.html`
  - `tests/api_integration/test_e2e_example_client.py`
- Affected APIs (e2e client side):
  - `GET /api/runs/{request_id}/events`（保持）
  - `GET /api/runs/{request_id}/events/history`（已具备，供 `raw_ref/relation` 与补偿逻辑消费）
  - `GET /api/runs/{request_id}/logs/range`（已具备，供 `raw_ref` 回跳消费）
  - `GET /api/runs/{request_id}/pending` 与 `POST /api/runs/{request_id}/reply` 对 installed/temp 均可用（source-aware 转发）
- Affected docs:
  - `docs/e2e_example_client_ui_reference.md`
