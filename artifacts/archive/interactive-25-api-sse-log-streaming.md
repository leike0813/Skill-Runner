# interactive-25-api-sse-log-streaming 实现记录

## 变更范围
- 新增 SSE 事件流端点：
  - `GET /v1/jobs/{request_id}/events`
  - `GET /v1/temp-skill-runs/{request_id}/events`
  - 统一事件类型：`snapshot/stdout/stderr/status/heartbeat/end`
  - 支持重连 offset：`stdout_from`、`stderr_from`
- `run_observability` 增量流能力：
  - 新增按 offset 增量读取：`read_log_increment`
  - 新增 SSE 事件生成器：`iter_sse_events`
  - 新增 SSE 帧格式化：`format_sse_frame`
  - 支持分片上限（默认 8KB）、heartbeat、`waiting_user/terminal` 结束语义
- 兼容性保持：
  - `GET /logs` 原有全量返回不变
  - UI `logs/tail` 行为不变（未改 UI 路由契约）
- 文档更新：
  - `docs/api_reference.md` 增加 SSE 端点、事件格式、offset 重连约定
  - `docs/dev_guide.md` 增加 `/events` 与 `/logs` 定位差异

## 测试与校验
- 定向单测：
  - `41 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit/test_run_observability.py tests/unit/test_v1_routes.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_temp_skill_runs_router.py -q`
- 全量单元测试：
  - `296 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit`
- 类型检查：
  - `Success: no issues found in 51 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate interactive-25-api-sse-log-streaming --type change --strict --no-interactive`
  - `openspec archive interactive-25-api-sse-log-streaming -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-25-api-sse-log-streaming`
